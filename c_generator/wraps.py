__all__ = [
    "FunctionWrapper"
]

from io import (
    StringIO
)

from sys import (
    version_info
)

from .generator import (
    FunctionBody
)
from .opt import (
    optimize_function
)

class OutputWrapper:

    def __init__(self, tab_size = 4):
        self.res = StringIO()
        self.cur_indent = ""
        self.tab = " " * tab_size
        self.tab_size = tab_size

    def indent(self):
        self.write(self.cur_indent)

    def push(self):
        self.cur_indent = self.cur_indent + self.tab

    def pop(self):
        self.cur_indent = self.cur_indent[:-self.tab_size]

    if version_info.major == 3:

        def write(self, data):
            self.res.write(data)

    else:

        def write(self, data):
            self.res.write(unicode(data))

    def getvalue(self):
        return str(self.res.getvalue())


class FunctionWrapper:
    @staticmethod
    def connect(modelFunction):
        gf = FunctionBody(modelFunction.name)
        modelFunction.body = FunctionWrapper(gf)
        return gf

    def __init__(self, genFunction):
        self.f = genFunction
        self.res = OutputWrapper()

    def __str__(self):
        optimize_function(self.f)
        self.f.out(self.res)
        return self.res.getvalue()
