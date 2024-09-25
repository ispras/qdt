__all__ = [
    "Block"
  , "BlockParser"
  , "Line"
]


class Block(list):
    heading = None


class Line(list):
    parent = None
    child = None
    n = None

    def __str__(self):
        return "".join(self)

    def __repr__(self):
        return type(self).__name__ + ' "%s"' % str(self).replace('"', '\\"')


class BlockParser(object):

    Block = Block
    Line = Line

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

        self._finalize_stack_top(0)

        # vheading is a virtual line, not existing in the `data`.
        # Its `child` is `Block` containing all items found in the `data`.
        return self.vheading

    def INIT(self, c):
        self.vheading = vheading = Line()
        self.stack = [(tuple(), vheading, [])]
        self.indent = []
        self.line = []
        self.line_n = 1

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
        n = self.line_n
        self.line_n = n + 1

        indent = tuple(self.indent)
        self.indent = []
        line = self.Line(self.line)
        self.line = []

        stack = self.stack

        if not (indent or line):
            # ignore blank lines
            return

        line.n = n

        for i, (block_indent, __, block) in enumerate(stack):
            if block_indent == indent:
                block.append(line)
                break
        else:
            block_1 = stack[-1][-1]
            if not block_1:
                raise SyntaxError("Indented line at the beginning of data")
            stack.append((indent, block_1[-1], [line]))
            return

        self._finalize_stack_top(i + 1)

    def _finalize_stack_top(self, i):
        stack = self.stack
        ready_blocks = stack[i:]
        del stack[i:]

        for __, heading, block in reversed(ready_blocks):
            block = self.Block(block)
            for line in block:
                line.parent = block
            block.heading = heading
            heading.child = block
