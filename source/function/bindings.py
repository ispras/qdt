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


class BodyTree(Node):

    def __init__(self):
        super(BodyTree, self).__init__()
        self.res = CodeWriter(backend = StringIO())
        # First child in BodyTree must have indent
        # That is why we set True to new_line
        self.res.new_line = True

    def __str__(self):
        self.__c__(self.res)
        return self.res.w.getvalue()

    def __c__(self, writer):
        self.out_children(writer)
