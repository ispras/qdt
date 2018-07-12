__all__ = [
    "CodeWriter"
]

class CodeWriter(object):
    """Helper for writing program code.

    Supports:
    - indentation
    - UTF-8 encoding
    """

    def __init__(self, backend = None, indent = "    "):
        """
        :backend: is a "writer" that will be given an output produced by this
            instance. It must implement `write` method for byte data.

        :indent: is string value of single indentation step.
        """

        self.indent = indent.encode("utf-8")
        self.w = backend

        self.reset()

    def reset(self):
        """Resets current indent to empty string and starts new line *without*
        outputting new line marker.
        """

        self.current_indent = b""
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

        self._write_enc(suffix + "\n")

    def write(self, string = ""):
        """ Appends :string: to current line.

        If current line has been just started then current indent will be
        written before the :string:.
        """

        if self.new_line:
            self.w.write(self.current_indent)
            self.new_line = False

        self._write_enc(string)

    def push_indent(self):
        "Increases current indent by one indentation step."

        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        "Decreases current indent by one indentation step."

        self.current_indent = self.current_indent[:-len(self.indent)]

    def _write_enc(self, string):
        self.w.write(string.encode("utf-8"))
