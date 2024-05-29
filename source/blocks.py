__all__ = [
    "Block"
  , "BlockParser"
  , "Line"
]


class Block(list):
    heading = None


class Line(list):
    block = None
    subblock = None

    def __str__(self):
        return "".join(self)

    def __repr__(self):
        return type(self).__name__ + ' "%s"' % str(self).replace('"', '\\"')


class BlockParser(object):

    @staticmethod
    def is_indent(c):
        return c in "\t "

    @staticmethod
    def is_cr(c):
        return c == "\r"

    @staticmethod
    def is_nl(c):
        return c == "\n"

    def __init__(self):
        pass

    def parse(self, data):
        state = self.INIT

        for c in data:
            state = state(c)

        return self.stack[0][1]

    def INIT(self, c):
        self.stack = [(tuple(), Block())]
        self.indent = []
        self.line = Line()

        return self.INDENT(c)

    def INDENT(self, c):
        if self.is_indent(c):
            self.indent.append(c)
            return self.INDENT

        if self.is_cr(c):
            self._line_end()
            return self.CR

        if self.is_nl(c):
            self._line_end()
            return self.INDENT

        self.line.append(c)
        return self.LINE

    def CR(self, c):
        if self.is_nl(c):
            return self.INDENT

        if self.is_indent(c):
            self.indent.append(c)
            return self.INDENT

        self.line.append(c)
        return self.LINE

    def LINE(self, c):
        if self.is_cr(c):
            self._line_end()
            return self.CR

        if self.is_nl(c):
            self._line_end()
            return self.INDENT

        self.line.append(c)
        return self.LINE

    def _line_end(self):
        indent = tuple(self.indent)
        self.indent = []
        line = self.line
        self.line = Line()

        stack = self.stack

        for i, (block_indent, block) in enumerate(stack):
            if block_indent == indent:
                block.append(line)
                line.block = block
                del stack[i + 1:]
                break
        else:
            line.block = block = Block([line])
            block_1 = stack[-1][1]
            if not block_1:
                raise SyntaxError("Indented line at the beginning of data")
            heading = block_1[-1]
            heading.subblock = block
            stack.append((indent, block))
