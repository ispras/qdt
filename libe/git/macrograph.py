__all__ = [
    "gen_gv"
  , "GitMgNode"
  , "GitMgEdge"
  , "GitMacrograph"
]

from common.git_tools import (
    co_build_git_graph,
    CommitDesc,
)
from common.lazy import (
    lazy
)
from common.notifier import (
    notifier,
)

from collections import (
    defaultdict,
)
from graphviz import (
    Digraph,
)


def gen_gv(g, init_gv = None):
    """ Given GitMacro`g`raph, generates `graphviz.Digraph`.
Returned graph can be configured by passing configured `init_gv`,
 it's used inplace and returned.
    """
    if not g.built:
        raise RuntimeError("first finish co_built")

    if init_gv is None:
        gv = Digraph(
            name = "Git Macrograph",
            graph_attr = dict(
                rankdir = "BT",
            ),
            node_attr = dict(
                shape = "polygon",
                fontname = "Momospace",
            ),
            edge_attr = dict(
                style = "filled"
            ),
        )
    else:
        gv = init_gv

    # cache
    node = gv.node
    edge = gv.edge
    edges = g._edges

    # macrograph nodes to Graphviz nodes
    mg2gv = {}

    for mn in edges:
        gvn = "n%d" % len(mg2gv)
        mg2gv[mn] = gvn
        label = mn.pretty
        node(gvn, label = label)

    # mn2dmns: MacroNode to Descendant MacroNodeS (edges from a `mn`. key)
    for mn2dmns in edges.values():
        for e in mn2dmns:
            if e:
                # commit sequence between macro nodes
                gve = "s%d" % len(mg2gv)
                mg2gv[e] = gve
                node(gve, label = str(len(e)))
                edge(mg2gv[e._ancestor], gve)
                edge(gve, mg2gv[e._descendant])
            else:
                edge(mg2gv[e._ancestor], mg2gv[e._descendant])

    return gv


_empty_tuple = tuple()

class GitMgNode(CommitDesc):
    """
Notes:

- A macronode is a commit with some non-regularity.
    E.g. tag or head.
    Roots, forks & merges are macronodes too.

- `_edge` attribute refers to `GitMgEdge` that node belongs to.
    It's `None` for macronodes.

    """

    def __init__(self, mg, sha, **kw):
        super(GitMgNode, self).__init__(sha, **kw)
        self._mg = mg

    def add_child(self, *a, **kw):
        super(GitMgNode, self).add_child(*a, **kw)
        if self.is_fork:
            self._mg._account_macronode(self)
        else:
            # Some macronodes may have no known children yet at moment of
            # first accounting.
            # E.g. root, head/tag at straight commit sequence.
            # The child added (just found) must start new edge construction.
            self._mg._account_if_macronode(self)

    @lazy
    def refs(self):
        refs = self._mg._sha2ref.get(self.sha)
        if refs:
            return tuple(refs)
        else:
            return _empty_tuple

    def iter_pretty_lines(self, indent = "\t", sha_part = 8):
        tags = []
        remotes = defaultdict(list)
        local_heads = []

        for r in self.refs:
            piter = iter(r.path.split("/"))
            assert next(piter) == "refs"  # drop
            t = next(piter)
            if t == "tags":
                tags.append(next(piter))
            elif t == "remotes":
                remotes[next(piter)].append(next(piter))
            else:
                if t != "heads":
                    print("Unexpected head type: " + t)
                local_heads.append(next(piter))

        yield str(self.sha[:sha_part])

        for h in sorted(local_heads):
            yield h

        for t in sorted(tags):
            yield t

        for r, r_heads in sorted(tuple(remotes.items())):
            yield r + "/"
            for rh in sorted(r_heads):
                yield indent + rh

    def gen_pretty(self, **kw):
        return "\n".join(self.iter_pretty_lines(**kw))

    @lazy
    def pretty(self):
        return self.gen_pretty()

    @property
    def is_macronode(self):
        return self in self._mg._edges

    _edge = None


class GitMgEdge(list):
    """ It's a sequence of commits (from `all_nodes`) between macronodes.

Notes:

- `_ancestor` attribute refers to parent (a macronode) of first node.

- `_descendant` attribute refers to child (a macronode) of last node.

    """
    __hash__ = lambda self: id(self)


@notifier(
    "node",  # GitMacrograph, GitMgNode
    "edge",  # GitMacrograph, GitMgEdge, NoneType/GitMgEdge (split)
)
class GitMacrograph(object):

    def __init__(self, repo):
        self._repo = repo

    def _node_factory(self, sha):
        node = GitMgNode(self, sha)
        if sha in self._sha2ref:
            self._account_macronode(node)  # tag/head
        else:
            commit = self._repo.commit(sha)
            parents = commit.parents
            if not parents:  # a root
                self._account_macronode(node)
            elif len(parents) > 1:  # a merge
                self._account_macronode(node)
            # Note, children are not known right now.
            # So, fork macronodes are detected by `GitMgNode.add_child`
            #   at runtime of `co_build`.
        return node

    built = False

    def co_build(self, **kw):
        repo = self._repo
        s2r = defaultdict(list)
        for r in repo.references:
            s2r[r.commit.hexsha].append(r)
        self._sha2ref = dict(s2r)

        # Keys are macronodes (`GitMgNode`).
        # Values are `set`s of `GitMgEdge`
        self._edges = defaultdict(set)

        self._all_nodes = all_nodes = {}

        self._edges2build = []

        yield True

        for co_bgg_ready in co_build_git_graph(repo, all_nodes,
            node_factory = self._node_factory,
            **kw
        ):
            yield self._co_build_edges()
            yield co_bgg_ready

        # process edges added during last iteration
        yield self._co_build_edges()

        self.built = True

    def _co_build_edges(self):
        # cache
        edges2build = self._edges2build
        edges = self._edges

        while edges2build:
            yield True
            e = edges2build.pop()

            last_c = e[-1]
            while True:
                children = last_c.children

                assert len(children) == 1

                last_c = children[0]
                if last_c in edges:
                    # new last_c is a macronode, the `e`dge ends here
                    e._descendant = last_c
                    self.__notify_edge(self, e, None)
                    break
                else:
                    # continue `e`dge construction
                    last_c._edge = e
                    e.append(last_c)

    # Note: This method must return as fast as possible!
    #     ` All intensive work must be delegated to `co_build`.
    def _account_macronode(self, mn):
        edges = self._edges
        e2b = self._edges2build

        if mn not in edges:
            print("macronode: ", mn.sha, " total: ", len(edges) + 1)
            self.__notify_node(self, mn)

        # edges from macronode `mn` to its descendant macronodes
        mn2dmns = edges[mn]

        e = mn._edge

        if e is not None:
            # print("a macronode is detected on edge")
            assert mn.is_fork

            try:
                e2b.remove(e)
            except ValueError:
                # print("that edge is already built")
                # split in 2 edges
                # TODO: Edge splittimg may take a while on long edges.
                #       Consider moving this action to `co_build`, like edge
                #       construction.
                i = e.index(mn)
                e2 = GitMgEdge(e[i+1:])
                del e[i:]
                for n in e2:
                    n._edge = e2
                e2._ancestor = mn
                e2._descendant = e._descendant
                e._descendant = mn

                assert not mn2dmns
                mn2dmns.add(e2)

                self.__notify_edge(self, e2, e)
            else:
                # print("that edge is not yet built")
                # Because `mn` is a node the edge entering. the edge is
                # considered built.
                # Note. there are no intermediate commits.
                assert len(e) == 1
                e.pop()
                e._descendant = mn
                self.__notify_edge(self, e, None)

            del mn._edge

        while len(mn2dmns) < len(mn.children):
            # begin edge construction for new children
            for c in mn.children:
                # try to find an edge containing this `c`hild
                for e in mn2dmns:
                    # A `c`hild can be another macronode so edge between
                    # is empty but have `_descendant is c`.
                    if e:
                        if e[0] is c:
                            assert c not in edges
                            break
                    else:
                        if e._descendant is c:
                            assert c in edges
                            break
                else:
                    e = GitMgEdge()
                    e._ancestor = mn
                    if c in edges:
                        # Child is a macronode too.
                        e._descendant = c
                        self.__notify_edge(self, e, None)
                    else:
                        c._edge = e
                        e.append(c)
                        e2b.append(e)
                    mn2dmns.add(e)

    def _account_if_macronode(self, n):
        if n in self._edges:
            self._account_macronode(n)

    gen_gv = gen_gv
