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
    Function
)
from .opt import (
    optimize_function
)

class OutputWrapper:
    def __init__(self):
        self.res = StringIO()

    def write(self, data):
        if version_info.major == 3:
            self.res.write(data)
        else:
            self.res.write(unicode(data))

    def getvalue(self):
        return str(self.res.getvalue())


class FunctionWrapper:
    @staticmethod
    def connect(modelFunction):
        gf = Function(modelFunction.name)
        modelFunction.body = FunctionWrapper(gf)
        return gf

    def __init__(self, genFunction):
        self.f = genFunction
        self.res = OutputWrapper()

    def __str__(self):
        optimize_function(self.f)
        self.f.out(self.res)
        return self.res.getvalue()
