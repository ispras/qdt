# TODO: support types

__all__ = [
    "Late"
  , "LateLinker"
      , "FuncLateLinker"
]

from common import (
    DictStack,
)
from .function.tree import (
    CBlock,
    define_python_operators,
)
from .model import (
    NodeVisitor,
    Variable,
)


@define_python_operators
class Late(object):

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class LateLinker(NodeVisitor):

    def __init__(self, root, **glob_ns):
        super(LateLinker, self).__init__(root)
        # Don't try `Namespace(glob_ns)`, `pop_ns` must `raise AttributeError`
        # on "stack" underflow.
        ns = DictStack()
        ns.update(glob_ns)
        self.ns = ns

    def _push_ns(self):
        self.ns = DictStack(self.ns)

    def _pop_ns(self):
        self.ns = self.ns.backing

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Late):
            self.replace(self.ns[cur.name])
            assert False  # no return

        if isinstance(cur, Variable):
            self.ns[cur.name] = cur
            return

        if isinstance(cur, CBlock):
            self._push_ns()
            return

    def on_leave(self):
        if isinstance(self.cur, CBlock):
            self._pop_ns()


class FuncLateLinker(LateLinker):

    def __init__(self, func, **glob_ns):
        for arg in func.args or ():
            glob_ns[arg.name] = arg
        super(FuncLateLinker, self).__init__(func.body, **glob_ns)
        self.function = func
