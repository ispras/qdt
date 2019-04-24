__all__ = [
    "CodeWriter"
  , "LanguageState"
]


class LanguageState(object):

    def __init__(self, writer, indent, prefix = None):
        self.w = writer

        self.prefix = prefix or ""
        self.indent = indent

        self._indents_stack = []
        self._states_stack = []

        self.reset()

    def reset(self):
        self._indents_stack[:] = []
        self.current_indent = ""
        self._states_stack[:] = []

    def __enter__(self):
        self._states_stack.append(self.w.s)
        self.w.s = self
        return self.w

    def __exit__(self, *_): # value, traceback
        self.w.s = self._states_stack.pop()

    def push_indent(self):
        "Increases current indent by one indentation step."

        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        "Decreases current indent by one indentation step."

        self.current_indent = self.current_indent[:-len(self.indent)]

    def save_indent(self, reset = True):
        "Saves current indent."

        self._indents_stack.append(self.current_indent)
        if reset:
            self.current_indent = ""

    def load_indent(self):
        "Loads previous indent."

        if self._indents_stack:
            self.current_indent = self._indents_stack.pop()
        else:
            raise RuntimeError("Cannot load previous indent: stack is empty")


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

        self.reset()

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

    def push_indent(self):
        "Increases current indent by one indentation step."

        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        "Decreases current indent by one indentation step."

        self.current_indent = self.current_indent[:-len(self.indent)]
