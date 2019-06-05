__all__ = [
    "CodeWriter"
  , "LanguageState"
]


class LanguageState(object):

    def __init__(self, writer, indent, prefix = None):
        self.w = writer

        self.prefix = prefix or ""
        self.indent = indent

        # Stack of indents?
        self.indents = []
        # Stack of states?
        self._previous = []

        self.reset()

    def reset(self):
        self.indents[:] = []
        self.current_indent = ""
        self._previous[:] = []

    def __enter__(self):
        self._previous.append(self.w.s)
        self.w.s = self
        return self.w

    def __exit__(self, e, *_): # value, traceback
        # XXX: e is not used too
        self.w.s = self._previous.pop()

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

        self.w = backend

        self._langs = {None: LanguageState(self, indent)}

        self.reset()

    def reset(self):
        """ Resets all language states, sets current state to default and
        starts new line *without* outputting new line marker.
        """

        for lang in self._langs.values():
            lang.reset()

        self.s = self._langs[None]

        self.new_line = False

    def line(self, suffix = ""):
        """ Appends :suffix: and finalizes current line.

        If current line has been just started then current indent will be
        written before the :suffix:.
        """

        if self.new_line:
            self.w.write(self.s.prefix)
            self.w.write(self.s.current_indent)
        else:
            self.new_line = True

        self.w.write(suffix + "\n")

    def write(self, string = ""):
        """ Appends :string: to current line.

        If current line has been just started then current indent will be
        written before the :string:.
        """

        if self.new_line:
            self.w.write(self.s.prefix)
            self.w.write(self.s.current_indent)
            self.new_line = False

        self.w.write(string)

    def push_indent(self):
        # TODO: revert comment?
        self.s.push_indent()

    def pop_indent(self):
        # TODO: revert comment?
        self.s.pop_indent()

    def save_indent(self, reset = True):
        # TODO: add comment?
        self.s.save_indent(reset)

    def load_indent(self):
        # TODO: add comment?
        self.s.load_indent()

    def add_lang(self, lang_name, indent, prefix = None):
        "Adds language."

        self._langs[lang_name] = LanguageState(self, indent, prefix)

    def __getattr__(self, name):
        "Assume an undefined attribute to be one of language states."

        d = self.__dict__
        try:
            return d[name]
        except KeyError:
            try:
                return d["_langs"][name]
            except KeyError:
                return super(CodeWriter, self).__getattr__(name)
