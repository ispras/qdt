__all__= [
    "DynamicGraphPlacer2D"
  , "iter_8_dirs"
]

from ..common.astar import (
    a_iter_reversed,
    CoAStep,
    co_a_star,
)
from ..common.attr_change_notifier import (
    AttributeChangeNotifier,
)
from common.co_dispatcher import (
    callco,
    CoReturn,
)
from ..common.grid import (
    Grid,
)
from ..common.diag_xy import (
    iter_diag_xy,
)

from collections import (
    defaultdict,
    deque,
)
from itertools import (
    chain,
)


# Private, never use externally.
_EMPTY_TUPLE = tuple()


class _Component(AttributeChangeNotifier):

    def __init__(self, placer, node, ij):
        self._placer = placer

        self._ij = ij

        self._nodes = {
            node: (0, 0)
        }
        self._free_components = set()
        self._edges = set()

        self._equeue = deque()
        self._mqueue = deque()

        self.aabb = (
            # screen coordinates
            0,  # left
            0,  # top
            1,  # just after right
            1   # hust after bottom
        )

        # A point in grid may have noting, one node only, one node and one
        # edge starting/ending at that node, one edge or several
        # crossing/collinear edges.
        # Other variants are the algorithm errors.
        self._grid = g = defaultdict(set)
        g[(0, 0)].add(node)

    @property
    def aabb(self):
        return self._aabb

    @aabb.setter
    def aabb(self, aabb):
        self._aabb = aabb
        l, t, r, b = aabb
        self.size = (r - l, b - t)

    def __contains__(self, n):
        if n in self._nodes:
            return True
        for c in chain(self._free_components, self._mqueue):
            if n in c:
                return True
        return False

    def __lt__(self, c):
        # Only placed nodes are relevant.
        # And only nodes.
        return len(self._nodes) < len(c._nodes)

    def __iter__(self):
        return chain(
            self._nodes,
            chain(*self._free_components),
            chain(*self._mqueue),
        )

    def __bool__(self):
        return bool(self._nodes or self._free_components or self._mqueue)

    def add_edge(self, e):
        self._equeue.append(e)

    def _remove_edge(self, e):
        l, t, r, b = self.aabb
        r -= 1
        b -= 1
        aabb_definetly_valid = True

        self._edges.remove(e)
        g = self._grid
        for coords in e:
            items = g[coords]
            items.remove(e)

            if not items:
                del g[coords]

            if aabb_definetly_valid:
                x, y = coords
                if x == l or x == r or y == t or y == b:
                    aabb_definetly_valid = False

        return aabb_definetly_valid

    def remove_node(self, n):
        coords = self._nodes.pop(n, None)
        if coords is None:
            # in _free_components/_mqueue
            for c in self._mqueue:
                if n in c:
                    c.remove_node(n)
                    if not c:
                        self._mqueue.remove(c)
                    break
            else:
                # in _free_components
                for c in self._free_components:
                    if n in c:
                        c.remove_node(n)
                        if not c:
                            self._free_components.remove(c)
                        break
        else:
            # placed already
            update_aabb = False

            cell = self._grid[coords]
            for e in tuple(cell):
                if isinstance(e, _Edge):
                    if not self._remove_edge(e):
                        update_aabb = True

            # Do this after last `remove_edge`.
            self._grid.pop(coords)

            if update_aabb:
                self._update_aabb()

        self._equeue = deque(e for e in self._equeue if n not in e)

    def _update_aabb(self):
        gter = iter(self._grid)

        try:
            l, t = next(gter)
        except StopIteration:
            self.aabb = (0, 0, 0, 0)
            return

        r = l
        b = t

        for x, y in gter:
            if x < l:
                l = x
            elif r < x:
                r = x
            if y < t:
                t = y
            elif b < y:
                b =  y

        self.aabb = (l, t, r + 1, b + 1)

    def merge(self, c):
        self._mqueue.append(c)

    @property
    def has_work(self):
        return bool(self._equeue or self._mqueue)

    # TODO: Is it worth to split different queues processing in
    #       specific `co`routines
    def co_work(self):
        nodes = self._nodes

        mq = self._mqueue
        next_m = mq.popleft

        while mq:
            yield True
            c = next_m()

            self._free_components.add(c)

            while c.has_work:
                yield c.co_work()

        eq = self._equeue
        next_e = eq.popleft

        while eq:
            yield True
            a, b = e = next_e()

            if a in nodes:
                if b in nodes:
                    yield self._co_route_edge(a, b, backward = False)
                else:
                    # b in a component
                    bc = (yield self._co_find_component_with_node(b))
                    if bc is None:
                        raise RuntimeError("unknown node %s" % b)
                    yield self._co_route_component(a, b, bc, backward = False)
            elif b in nodes:
                # a in a component
                ac = (yield self._co_find_component_with_node(a))
                if ac is None:
                    raise RuntimeError("unknown node %s" % a)
                yield self._co_route_component(b, a, ac, backward = True)
            else:
                # Both nodes are in components.
                # Wait until at least one of them is linked with an already
                # placed nodes
                # TODO: a dedicated container for "waiting" edges?
                eq.append(e)

    def _co_find_component_with_node(self, n):
        for c in self._free_components:
            yield True
            if n in c:
                raise CoReturn(c)

    def _co_route_component(self, begin, end, component, backward = False):
        ctx = _ComponentPlacingContext(self, component, begin, end, backward)
        start = _ComponentPlacingStep(
            ctx = ctx,
            xy = self._nodes[begin],
        )
        yield start.co_a_star()

    def _co_route_edge(self, begin, end, backward = False):
        ctx = _NodeJoiningContext(self, end, backward)
        start = _NodeJoiningStep(
            ctx = ctx,
            xy = self._nodes[begin],
        )
        yield start.co_a_star()

    def _co_embed_component(self, c, xy):
        self._free_components.update(c._free_components)
        self._equeue.extend(c._equeue)
        self._mqueue.extend(c._mqueue)

        yield self._co_place_component(c, *xy)

    def _co_place_component(self, c, x, y):
        l, t, r, b = self.aabb
        cl, ct, cr, cb = c.aabb

        if x is None:
            x = l
            if cl < 0:
                x -= cl  # += |cl|

        if y is None:
            y = b + 1

            if ct < 0:
                y -= ct  # += |ct|

        grid = self._grid
        nodes = self._nodes

        for cn, (cnx, cny) in c._nodes.items():
            yield True
            nx = cnx + x
            ny = cny + y
            nxy = (nx, ny)
            nodes[cn] = nxy
            grid[nxy].add(cn)

        edges = self._edges
        for ce in c._edges:
            yield True
            e = _Edge((cex + x, cey + y) for (cex, cey) in ce)
            edges.add(e)
            for exy in e:
                grid[exy].add(e)

        self.aabb = (
            min(l, cl + x),
            min(t, ct + y),
            max(r, cr + x),
            max(b, cb + y)
        )


class _Edge(tuple):
    pass


class _StepForbidden(BaseException):
    "not a failure"


class _PlacingContext(object):

    def __init__(self, component, target, backward):
        self.component = component
        self.placer = placer = component._placer
        self.grid = component._grid
        pd = placer.preferred_direction
        self.preferred_dir = (-pd[0], -pd[1]) if backward else pd
        self.target_xy = component._nodes[target]
        self.backward = backward
        self.reached = {}

    def _co_try_end(self, step):
        raise NotImplementedError

    def _co_place_edge(self, end_step):
        if self.backward:
            e = _Edge(s.xy for s in a_iter_reversed(end_step))
        else:
            reversed_steps = tuple(a_iter_reversed(end_step))
            e = _Edge(s.xy for s in reversed(reversed_steps))

        yield True

        component = self.component

        l, t, r, b = component.aabb
        upd = False

        component._edges.add(e)
        grid = self.grid
        for xy in e:
            grid[xy].add(e)
            x, y = xy

            if x < l:
                l = x
                upd = True
            elif r <= x:
                r = x + 1
                upd = True

            if y < t:
                t = y
                upd = True
            elif b <= y:
                b = y + 1
                upd = True

        if upd:
            component.aabb = (l, t, r, b)

        raise CoReturn(e)


class _PlacingStep(CoAStep):

    def __init__(self, ctx, xy, w = 0, d = None, r = None):
        """
@param w:
    total weight of the path candidate
@param d:
    direction, used to add rotation penalty to total weight
@param r:
    target point distance penalty, part of `w`eight
        """

        self.ctx = ctx
        self.xy = xy
        self.d = ctx.preferred_dir if d is None else d
        if r is None:
            tx, ty = ctx.target_xy
            x, y = xy
            r = abs(tx - x) + abs(ty - y)
            w += r
        self.r = r
        self.w = w

    def co_a_star(self):
        yield co_a_star(self)

    def __co_try_end__(self):
        return self.ctx._co_try_end(self)

    def __str__(self):
        return repr(self.xy)

    def __lt__(self, step):
        return self.w < step.w

    def __iter_steps__(self):
        # print(self.w + self.r, self.a_star_path_str())

        c = self.ctx
        x, y = self.xy
        tx, ty = c.target_xy
        reached = c.reached

        for sd in iter_8_dirs():
            sdx, sdy = sd  # step direction
            sx = x + sdx
            sy = y + sdy
            s = sx, sy

            sr = abs(sx - tx) + abs(sy - ty)

            try:
                sw = self.w + self.__step_penalty__(s, sd)
            except _StepForbidden:
                continue

            sw += sr - self.r

            # drop paths those reach the point `s` not having less `w`eight
            if s in reached:
                if reached[s] <= sw:
                    continue

            reached[s] = sw

            yield type(self)(c, s, sw, sd, sr)

    def __step_penalty__(self, s, sd):
        """
@param s:
    (x, y) of step
@param sd:
    (dx, dy) of step relative to self.xy
    I.e. sd = s - self.xy
@return penalty to total weight of path candidate
@raise _StepForbidden:
    The step is inacceptible.
        """
        return (
            self._step_position_penalty(s)
          + self._step_rotation_penalty(*sd)
          + self._step_direction_penalty(*sd)
        )

    def _step_position_penalty(self, s):
        # cache
        c = self.ctx
        txy = c.target_xy
        P_EDGE_INTERSECTION = c.placer.P_EDGE_INTERSECTION

        p = 0

        # check if step touching something in static grid
        for o in self.ctx.grid.get(s, _EMPTY_TUPLE):
            if isinstance(o, _Edge):
                # avoid edge crossing
                p += P_EDGE_INTERSECTION
            elif s != txy:
                # node touching is forbiddent, except target node
                raise _StepForbidden

        if self._touch_tail(s):
            raise _StepForbidden

        return p

    def _touch_tail(self, xy):
        for s in a_iter_reversed(self.__a_prev__):
            if s.xy == xy:
                return True

    def _step_rotation_penalty(self, sdx, sdy):
        # cache
        dx, dy = self.d

        p = 0
        # analyze edge line rotation

        scalar = dx * sdx + dy * sdy
        vector = dx * sdy - dy * sdx

        if vector:
            # non collinear
            if scalar > 0:
                p += self.ctx.placer.P_45_TURN
            elif scalar:  # scalar < 0
                # sw += 50  # 135 degrees turn
                raise _StepForbidden
            else:  # scalar == 0
                p += self.ctx.placer.P_90_TURN
        else:
            # collinear
            if scalar < 0:
                # sw += 100  # 180 degrees turn
                raise _StepForbidden
            else:
                p += self.ctx.placer.P_FORWARD

        return p

    def _step_direction_penalty(self, sdx, sdy):
        # account prefered direction

        # cache
        c = self.ctx
        pdx, pdy = c.preferred_dir

        p = 0
        # analyze edge line rotation

        scalar = sdx * pdx + sdy * pdy
        vector = sdx * pdy - sdy * pdx

        if vector:
            if scalar > 0:
                p += c.placer.P_45_DEVIATION
            elif scalar:
                p += c.placer.P_135_DEVIATION
            else:
                p += c.placer.P_90_DEVIATION
        else:
            if scalar < 0:
                p += c.placer.P_180_DEVIATION

        return p


class _NodeJoiningContext(_PlacingContext):

    def _co_try_end(self, s):
        txy = self.target_xy

        if s.xy != txy:
            return

        yield self._co_place_edge(s)

        # Finish A*
        raise CoReturn(True)


class _NodeJoiningStep(_PlacingStep):
    pass


class _ComponentPlacingContext(_PlacingContext):

    def __init__(self, to, what, begin, end, backward):
        """
@param bind_offset:
    Offset of placing point relative to (0, 0) of `bound_grid`.
        """
        super(_ComponentPlacingContext, self).__init__(to,
            # During component placing there is no a target (a node
            # the edge should reach).
            # Instead, we use `begin` (start point of the edge) as
            # `end` to place component as near as possible.
            # Reminder, distance to `end` is used to compute weight of
            # A* path.
            begin,
            backward,
        )
        self.placed = what
        self.bound_grid = what._grid
        self.bind_offset = what._nodes[end]

    def _co_try_end(self, s):
        x, y = s.xy

        # Only place nodes on even positions.
        # So, an edge can always be routed event if a node is surrounded by
        # 8 nodes.
        # Reminder, an edge cannot pass thorough a node.
        if x & 1 or y & 1:
            return

        box, boy = self.bind_offset
        bg = self.bound_grid
        sg = self.grid  # static grid

        for i, ((nx, ny), objs) in enumerate(bg.items()):
            if i & 0x40:  # pause
                yield True

            if not objs:
                continue

            for o in objs:
                if not isinstance(o, _Edge):
                    has_node = True
                    break
            else:
                has_node = False

            for o in sg.get((nx + x - box, ny + y - boy), _EMPTY_TUPLE):
                if has_node or not isinstance(o, _Edge):
                    # overlapping with a node, edges may overlaps
                    return

        to = self.component
        what = self.placed

        to._free_components.remove(what)

        yield self._co_place_edge(s)
        yield to._co_embed_component(what, (x - box, y - boy))

        # Finish A*
        raise CoReturn(True)


class _ComponentPlacingStep(_PlacingStep):

    def __step_penalty__(self, s, sd):
        return (
            super(_ComponentPlacingStep, self).__step_penalty__(s, sd)
          + self._bound_grid_overlapping_penalty(*s)
        )

    def _bound_grid_overlapping_penalty(self, sx, sy):
        """ Check if tail (including this step) will touch bound grid
when the `s`tep is made.
        """
        # cache
        c = self.ctx
        box, boy = c.bind_offset
        bg = c.bound_grid
        P_EDGE_INTERSECTION = c.placer.P_EDGE_INTERSECTION

        p = 0

        # coords of (0, 0) of bound grid relative to (0, 0) of static grid
        b0x = sx - box
        b0y = sy - boy

        for ts in a_iter_reversed(self):
            # coords of step relative to (0, 0) of static grid
            tsx, tsy = ts.xy

            # coords of step relative to (0, 0) of bound grid
            btsx = tsx - b0x
            btsy = tsy - b0y

            for o in bg.get((btsx, btsy), _EMPTY_TUPLE):
                if isinstance(o, _Edge):
                    # avoid edge crossing
                    p += P_EDGE_INTERSECTION
                else:
                    # node touching is forbiddent
                    raise _StepForbidden

        return p


def iter_8_dirs():
    yield  0, -1  # top
    yield  1, -1
    yield  1,  0  # right
    yield  1,  1
    yield  0,  1  # bottom
    yield -1,  1
    yield -1,  0  # left
    yield -1, -1


class DynamicGraphPlacer2D(object):

    # penalties
    P_EDGE_INTERSECTION = 4

    # edge straightness
    P_FORWARD = 1
    P_45_TURN = 2
    P_90_TURN = 4
    # note: 135, 180 turns are forbidden

    preferred_direction = (0, 1)  # top down

    P_45_DEVIATION = 1
    P_90_DEVIATION = 2
    P_135_DEVIATION = 3
    P_180_DEVIATION = 4

    # mathhack: use preferred_direction = (0, 0)
    #           to ignore preferred direction deviation penalties

    def __init__(self):
        # `n`odes & `e`dges accounting queues
        self._nqueue = deque()
        self._equeue = deque()

        # `n`ode -> `c`omponent
        self._n2c = {}
        # `c`omponents having to work
        self._cqueue = deque()

        # grid coordinates of components
        self._components = {}
        self._c_coord_gen = iter_diag_xy()

        self._g = Grid()

    def add_node(self, n):
        self._nqueue.append(n)

    def remove_node(self, n):
        # Note, `None` is valid `n`ode.
        # Use another (private) absence indicator.
        c = self._n2c.pop(n, _EMPTY_TUPLE)
        if c is _EMPTY_TUPLE:
            self._nqueue.remove(n)
        else:
            c.remove_node(n)
            if not c:
                del self._components[c._ij]
                self._g.remove(c)
                self._cqueue = deque(c0 for c0 in self._cqueue if c0 is not c)
        self._equeue = deque(e for e in self._equeue if n not in e)

    def add_edge(self, *ab):
        self._equeue.append(ab)

    def place(self):
        while self.has_work:
            callco(self.co_place())

    def co_place(self):
        # cache
        cq = self._cqueue
        g = self._g

        # Multiple enquques of a `_Component` are possible bellow.
        # This effectively raises "priority" of "hot" components.
        # I.e. that's a feature.
        enqueue = cq.append

        nq = self._nqueue
        next_n = nq.popleft
        n2c = self._n2c
        components = self._components
        c_coord_gen = self._c_coord_gen

        while nq:
            n = next_n()
            ij = next(c_coord_gen)
            c = _Component(self, n, ij)
            n2c[n] = c
            assert ij not in components
            components[ij] = c
            g.add(ij, c)

            enqueue(c)

        # cache
        eq = self._equeue
        if eq:
            next_e = eq.popleft
            yield True

        next_try = []

        while eq:
            a, b = e = next_e()

            # nodes and edges can be added between `yield`s
            try:
                try:
                    ac = n2c[a]
                except KeyError:
                    assert a in nq
                    raise
                try:
                    bc = n2c[b]
                except KeyError:
                    assert b in nq
                    raise
            except KeyError:
                next_try.append(e)
                continue

            if ac is bc:
                # already in same components
                ac.add_edge(e)
                enqueue(ac)
            else:
                yield True
                # in different components
                if ac < bc:
                    g.remove(ac)
                    del components[ac._ij]
                    bc.merge(ac)
                    enqueue(bc)
                    for n in ac:
                        n2c[n] = bc
                    bc.add_edge(e)
                else:
                    g.remove(bc)
                    del components[bc._ij]
                    ac.merge(bc)
                    enqueue(ac)
                    for n in bc:
                        n2c[n] = ac
                    ac.add_edge(e)

        eq.extend(next_try)

        if cq:
            yield True
            next_c = cq.popleft

        while cq:
            c = next_c()
            yield c.co_work()
            if c.has_work:
                enqueue(c)

    @property
    def has_work(self):
        return bool(self._cqueue or self._nqueue or self._equeue)

    _bg_working = False

    def co_place_bg(self):
        self._bg_working = True
        while self._bg_working:
            if self.has_work:
                # TODO: Is it worth to split different queues processing in
                #       specific `co`routines
                yield self.co_place()
            else:
                yield False

    def stop_bg(self):
        try:
            delattr(self, "_bg_working")
        except AttributeError:
            pass  # `co_place_bg`_bg has not been started.
