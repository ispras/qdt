__all__ = [
    "BodyTree"
]

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

    def __str__(self):
        res = CodeWriter(backend = StringIO())
        res.new_line = True
        self.__c__(res)
        return res.w.getvalue()

    def __c__(self, writer):
        self.out_children(writer)
