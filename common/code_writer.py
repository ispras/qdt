__all__ = [
    "CodeWriter"
]

class CodeWriter(object):
    """Helper for writing program code.

    Supports:
    - indentation
    """

    def __init__(self, backend = None, indent = "    "):
        """
        :backend: is a "writer" that will be given an output produced by this
            instance. It must implement `write` method for byte data.

        :indent: is string value of single indentation step.
        """

        self.indent = indent
        self.w = backend
        self.states = []

        self.reset()

    def reset(self):
        """Resets current indent to empty string and starts new line *without*
        outputting new line marker.
        """

        self.current_indent = ""
        self.new_line = False

    def line(self, suffix = ""):
        """ Appends :suffix: and finalizes current line.

        If current line has been just started then current indent will be
        written before the :suffix:.
        """

        if self.new_line:
            self.w.write(self.current_indent)
        else:
            self.new_line = True

        self.w.write(suffix + "\n")

    def write(self, string = ""):
        """ Appends :string: to current line.

        If current line has been just started then current indent will be
        written before the :string:.
        """

        if self.new_line:
            self.w.write(self.current_indent)
            self.new_line = False

        self.w.write(string)

    # TODO: args -> items
    # XXX: __c__ is too domain specific
    def join(self, delim, args, method = "__c__"):
        # TODO: a comment
        if args:
            first = args[0]
            getattr(first, method)(self)

            for a in args[1:]:
                self.write(delim)
                getattr(a, method)(self)

    def push_indent(self):
        "Increases current indent by one indentation step."

        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        "Decreases current indent by one indentation step."

        self.current_indent = self.current_indent[:-len(self.indent)]

    def push_state(self, reset = False):
        "Save current state"

        self.states.append((self.current_indent, self.new_line))
        if reset:
            self.reset()

    def pop_state(self):
        "Load previous state"

        if self.states:
            state = self.states.pop()
            self.current_indent = state[0]
            self.new_line = state[1]
        else:
            raise RuntimeError("Cannot load previous state - stack empty")
