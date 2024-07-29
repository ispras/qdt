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
    define_python_operators,
)
from .model import (
    Type,
    TypeReferencesVisitor,
    Variable,
)


@define_python_operators
class Late(object):

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


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

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Type):
            if cur.definer is not self.root:
                raise SkipVisiting
            # Some `Type`s have `Variable`s inside (Structure, Function).
            # Those `Variable`s are only visible in `Type`'s scope.
            self._push_ns()

        elif isinstance(cur, CBlock):
            self._push_ns()

        elif isinstance(cur, Variable):
            self.ns[cur.name] = cur

        elif isinstance(cur, Late):
            self.replace(self.ns[cur.name])
            assert False  # no return

    def on_leave(self):
        cur = self.cur

        if isinstance(cur, Type):
            if cur.definer is not self.root:
                return
            self._pop_ns()

        elif isinstance(cur, CBlock):
            self._pop_ns()
