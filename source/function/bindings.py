__all__ = [
    "BodyTree"
]

from .tree import (
    Declare,
    Node,
    OpAssign
)
from ..model import (
    Variable
)
from six import (
    StringIO
)
from common import (
    CodeWriter,
    ObjectVisitor,
)


class VarUsageAnalyzer(ObjectVisitor):

    def __init__(self, root):
        super(VarUsageAnalyzer, self).__init__(root,
            field_name = "__node__"
        )

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Variable):
            parent = self.path[-3][0]

            if isinstance(parent, Declare):
                return
            elif isinstance(parent, OpAssign):
                """ A variable in a function body is unused
                if it's at the left of an assignment inside a declaration.
                """
                parent_1 = self.path[-5][0]

                if isinstance(parent_1, Declare):
                    cur_idx = self.path[-1][1]
                    if cur_idx == 0:
                        return

            cur.used = True


class BodyTree(Node):

    def __init__(self):
        super(BodyTree, self).__init__()

    def __str__(self):
        VarUsageAnalyzer(self).visit()
        res = CodeWriter(backend = StringIO())
        res.new_line = True
        self.__c__(res)
        return res.w.getvalue()

    def __c__(self, writer):
        self.out_children(writer)
