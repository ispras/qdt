__all__ = [
    "CConst"
]


class CConst(object):
    def gen_c_code(self):
        "Implementation must return string compatible with C generator"
        raise NotImplementedError()

    # for usage in source.function.tree
    new_line = ";"

    def __c__(self, writer):
        writer.write(self.gen_c_code())

    def __ne__(self, v):
        "Explicit redirection for Py2."
        return not self.__eq__(v)

    def __gen_code__(self, gen):
        gen.line(repr(self))
