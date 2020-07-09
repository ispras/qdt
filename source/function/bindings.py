__all__ = [
    "BodyTree"
]

from .tree import (
    Declare,
    OpDeclareAssign,
    CNode
)
from ..model import (
    NodeVisitor,
    Variable
)
from six import (
    StringIO
)
from common import (
    CodeWriter
)
from .argument import (
    LateLinker,
)


class VarUsageAnalyzer(NodeVisitor):

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Variable):
            parent = self.path[-3][0]

            if isinstance(parent, Declare):
                return
            elif isinstance(parent, OpDeclareAssign):
                """ Presence of a function local variable at the left
                of an assignment inside a variable declaration is not a usage
                this analyzer does looking for.
                """
                cur_idx = self.path[-1][1]
                if cur_idx == 0:
                    return

            cur.used = True


class BodyTree(CNode):

    def __init__(self):
        super(BodyTree, self).__init__()

    def __str__(self):
        VarUsageAnalyzer(self).visit()
        cw = CodeWriter(backend = StringIO())
        cw.add_lang("c", "    ")
        cw.add_lang("cpp", "  ", "#")
        cw.new_line = True
        with cw.c:
            self.__c__(cw)
        return cw.w.getvalue()

    def __c__(self, writer):
        self.out_children(writer)

    @property
    def function(self):
        # Note, the attribute is not always assigned. So, `AttributeError`
        # should be expected by caller.
        return self._function

    @function.setter
    def function(self, function):
        LateLinker(self, function).visit()
        if hasattr(self, "_function"):
            raise NotImplementedError("Function changing is not implemented")
        self._function = function

    @function.deleter
    def function(self):
        raise NotImplementedError("Function changing is not implemented")
