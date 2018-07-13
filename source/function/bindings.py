__all__ = [
    "BodyTree"
]

from .tree import (
    Node,
    OpAssign,
    OpDeclare
)
from source import (
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

        '''If var is in the OpDeclare, var marked as used only
        if it is in the right part of the assignment '''
        if isinstance(cur, Variable):
            parent = self.path[-3][0]

            if isinstance(parent, OpAssign):
                parent_1 = self.path[-5][0]

                if isinstance(parent_1, OpDeclare):
                    cur_idx = self.path[-1][1]
                    if cur_idx == 0:
                        return

            cur.used = True


class BodyTree(Node):

    def __init__(self):
        super(BodyTree, self).__init__()
        self.res = CodeWriter(backend = StringIO())
        # First child in BodyTree must have indent
        # That is why we set True to new_line
        self.res.new_line = True

    def __str__(self):
        VarUsageAnalyzer(self).visit()
        self.__c__(self.res)
        return self.res.w.getvalue()

    def __c__(self, writer):
        self.out_children(writer)
