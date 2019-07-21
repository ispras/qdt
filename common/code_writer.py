__all__ = [
    "CodeWriter"
  , "LanguageState"
]


from six import (
    StringIO
)


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
            Default is StringIO.

        :indent: is string value of single indentation step.
        """

        if backend is None:
            backend = StringIO()

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
        If :string: is multilined then each line is prefixed with indent
        except _empty_ last line.
        """

        lines = string.split("\n")
        if len(lines) > 1:
            for l in lines[:-1]:
                self.line(l)
            string = lines[-1]
            if not string:
                return

        if self.new_line:
            self.w.write(self.s.prefix)
            self.w.write(self.s.current_indent)
            self.new_line = False

        self.w.write(string)

    def join(self, delim, items, out_method):
        "Prints items that are separated by a delimiter."

        if items:
            first = items[0]
            out_method(first, self)

            for a in items[1:]:
                self.write(delim)
                out_method(a, self)

    def push_indent(self):
        "Increases current indent by one indentation step."

        self.s.push_indent()

    def pop_indent(self):
        "Decreases current indent by one indentation step."

        self.s.pop_indent()

    def save_indent(self, reset = True):
        "Saves current indent."

        self.s.save_indent(reset)

    def load_indent(self):
        "Loads previous indent."

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
                # Note that`object` class has no  `__getattr__`.
                # See: https://stackoverflow.com/questions/28530982/why-is-object-getattr-missing
                return super(CodeWriter, self).__getattribute__(name)
