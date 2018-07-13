__all__ = [
    "BodyTree"
]

from .tree import (
    Node
)
from six import (
    StringIO
)
from common import (
    CodeWriter
)


class BodyTree(Node):

    def __init__(self):
        super(BodyTree, self).__init__()

    def __str__(self):
        cw = CodeWriter(backend = StringIO())
        cw.new_line = True
        self.__c__(cw)
        return cw.w.getvalue()

    def __c__(self, writer):
        self.out_children(writer)
