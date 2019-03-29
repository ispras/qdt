__all__ = [
    "CodeWriter"
]


class CodeWriter(object):
    """Helper for writing program code.

    Supports:
    - indentation
    """

    def __init__(self, backend = None):
        """
        :backend: is a "writer" that will be given an output produced by this
            instance. It must implement `write` method for byte data.
        """

        self.w = backend

        self.previous_states = [
            # indent, indents, prefix
            ["  ", [""], "#"], # CPP lang
            ["    ", [], ""] # C lang
        ]
        self.next_states = []

        self.load_state()

        self.reset()

    def load_state(self):
        "Loads current state."

        if self.previous_states:
            self.indent, self.indents, self.prefix = self.previous_states[-1]
        else:
            raise RuntimeError("Cannot load current state - stack empty")

    def reset(self):
        """ Resets current indent to empty string and starts new line *without*
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
            self.w.write(self.prefix)
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
            self.w.write(self.prefix)
            self.w.write(self.current_indent)
            self.new_line = False

        self.w.write(string)

    def push_indent(self):
        "Increases current indent by one indentation step."

        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        "Decreases current indent by one indentation step."

        self.current_indent = self.current_indent[:-len(self.indent)]

    def save_indent(self, reset = True):
        "Saves current indent."

        self.indents.append(self.current_indent)
        if reset:
            self.current_indent = ""

    def load_indent(self):
        "Loads previous indent."

        if self.indents:
            self.current_indent = self.indents.pop()
        else:
            raise RuntimeError("Cannot load previous indent - stack empty")

    def __enter__(self):
        "Switches to previous state."

        if self.previous_states:
            self.save_indent()
            self.next_states.append(self.previous_states.pop())
            self.load_state()
            self.load_indent()
        else:
            raise RuntimeError("Cannot save previous state - stack empty")

        return self

    def __exit__(self, e, *_): # value, traceback
        "Switches to next state."

        if self.next_states:
            self.save_indent()
            self.previous_states.append(self.next_states.pop())
            self.load_state()
            self.load_indent()
        else:
            raise RuntimeError("Cannot load next state - stack empty")
