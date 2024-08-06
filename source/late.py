__all__ = [
    "Late"
  , "LateLinker"
]

from common import (
    DictStack,
    SkipVisiting,
)
from .function.tree import (
    CBlock,
    CNode,
)
from .model import (
    Type,
    TypeReferencesVisitor,
    Variable,
)


class Late(CNode):

    __slots__ = ("name",)

    def __init__(self, name):
        super(Late, self).__init__()
        self.name = name

    def __call__(self, name, *a, **kw):
        "Emulate Type.__call__"
        return Variable(name, self, *a, **kw)

    def __c__(self, __):
        raise RuntimeError("%s: late linking failed" % self)

    def __repr__(self):
        return type(self).__name__ + "(%r)" % self.name


class LateLinker(TypeReferencesVisitor):

    def __init__(self, definer, **glob_ns):
        super(LateLinker, self).__init__(definer)
        # Don't try `Namespace(glob_ns)`, `pop_ns` must `raise AttributeError`
        # on "stack" underflow.
        ns = DictStack()
        ns.update(glob_ns)
        ns.update(definer.types)
        ns.update(definer.global_variables)
        self.ns = ns

    def _push_ns(self):
        self.ns = DictStack(self.ns)

    def _pop_ns(self):
        self.ns = self.ns.backing

    def __visit__(self, cur):
        if isinstance(cur, Type):
            if cur.definer is not self.root:
                raise SkipVisiting
            # Some `Type`s have `Variable`s inside (Structure, Function).
            # Those `Variable`s are only visible in `Type`'s scope.
            self._push_ns()

        elif isinstance(cur, CBlock):
            self._push_ns()

        elif isinstance(cur, Variable):
            # Note, `get` does not use `__missing__` of `DictStack`.
            # So, conflicts are only checked at top of namsapace stack.
            conflict = self.ns.get(cur.name, cur)
            if conflict is not cur:
                print("%s: conflict in namespace: %s is replaced with %s" % (
                    cur.name, conflict, cur
                ))
            self.ns[cur.name] = cur

        elif isinstance(cur, Late):
            # This could be declared late.
            try:
                # Note, don't use `get`.
                # It doesn't use `__missing__` of `DictStack`.
                # So, `get` misses outer namespace entries.
                rep = self.ns[cur.name]
            except KeyError:
                # This could be declared late.
                raise SkipVisiting
            else:
                self.replace(rep)
            assert False  # no return

    def __leave__(self, cur):
        if isinstance(cur, Type):
            if cur.definer is not self.root:
                return
            self._pop_ns()

        elif isinstance(cur, CBlock):
            self._pop_ns()
