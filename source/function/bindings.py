__all__ = [
    "BodyTree"
]

from .tree import (
    Declare,
    OpAssign,
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


class VarUsageAnalyzer(NodeVisitor):

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Variable):
            parent = self.path[-3][0]

            if isinstance(parent, Declare):
                return
            elif isinstance(parent, OpAssign):
                """ Presence of a function local variable at the left
                of an assignment inside a variable declaration is not a usage
                this analyzer does looking for.
                """
                parent_1 = self.path[-5][0]

                if isinstance(parent_1, Declare):
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
