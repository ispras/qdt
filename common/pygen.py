__all__ = [
    "PyGenerator"
]

from six import (
    text_type,
    binary_type,
    integer_types
)
from itertools import (
    count
)

if __name__ == "__main__":
    from sys import (
        stdout
    )
    from topology import (
        sort_topologically
    )
    from reflection import (
        get_class_total_args
    )
else:
    from .topology import (
        sort_topologically
    )
    from .reflection import (
        get_class_total_args
    )

const_types = (float, text_type, binary_type, bool) + integer_types

"""
PyGenerator provides an interface for saving an object to the file.
The file is to be a python script such that execution of the file will
reconstruct the object.
"""
class PyGenerator(object):
    def __init__(self, indent = "    "):
        self.indent = indent

        self.reset()

    def reset(self):
        self.obj2name = {}
        self.name2obj = {}
        self.name_counter = {}

        self.current_indent = ""
        self.new_line = False

    def line(self, suffix = ""):
        if self.new_line:
            self.write_enc(self.current_indent)
        else:
            self.new_line = True

        self.write_enc(suffix + "\n")

    def write(self, string = ""):
        if self.new_line:
            self.write_enc(self.current_indent)
            self.new_line = False

        self.write_enc(string)

    def write_enc(self, string):
        self.w.write(string.encode("utf-8"))

    def push_indent(self):
        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        self.current_indent = self.current_indent[:-len(self.indent)]

    def nameof(self, obj):
        if obj is None:
            return "None"

        if not obj in self.obj2name:
            try:
                var_base = obj.__var_base__
            except AttributeError:
                var_base = "obj"
            else:
                var_base = var_base()

            name = var_base

            if name in self.name2obj:
                for i in self.name_counter.setdefault(var_base, count(0)):
                    name = "%s%d" % (var_base, i)
                    if name not in self.name2obj:
                        break

            self.obj2name[obj] = name
            self.name2obj[name] = obj

        return self.obj2name[obj]

    def serialize(self, writer, root):
        self.w = writer
        self.reset()

        objects = sort_topologically([root])

        for o in objects:
            self.write(self.nameof(o) + " = ")
            try:
                gen_code = o.__gen_code__
            except AttributeError:
                print("Object %s of type %s does not provide __gen_code__" % (
                    str(o), type(o).__name__
                ))
                self.line("None")
            else:
                gen_code(self)
            self.line()

    def gen_const(self, c):
        # `bool` is an integer type (not in all Python versions probably) and
        # this type information must be preserved.
        if isinstance(c, bool):
            return str(c)
        elif isinstance(c, integer_types):
            if c <= 0:
                return "%d" % c
            else:
                return "0x%0x" % c
        elif isinstance(c, (binary_type, text_type)):
            normalized = ""
            prefix = ""
            multiline = False
            # Double and single quote count
            dquote = 0
            squote = 0
            for ch in c:
                code = ch if isinstance(ch, int) else ord(ch)

                if code > 0xFFFF: # 4-byte unicode
                    prefix = "u"
                    normalized += "\\U%08x" % code
                elif code > 0xFF: # 2-byte unicode
                    prefix = "u"
                    normalized += "\\u%04x" % code
                elif code > 127: # non-ASCII code
                    normalized += "\\x%02x" % code
                elif code == 92: # \
                    normalized += "\\\\"
                else:
                    if code == 34: # "
                        dquote += 1
                    elif code == 38: # '
                        squote += 1
                    elif code == 0x0A or code == 0x0D:
                        multiline = True
                    normalized += chr(code)

            if dquote > squote:
                escaped = normalized.replace("'", "\\'")
                quotes = "'''" if multiline else "'"
                return prefix + quotes + escaped + quotes
            else:
                escaped = normalized.replace('"', '\\"')
                quotes = '"""' if multiline else '"'
                return prefix + quotes + escaped + quotes
        else:
            return repr(c)

    def reset_gen(self, obj):
        self.reset_gen_common(type(obj).__name__ + "(")

    def reset_gen_common(self, prefix):
        self.first_field = True
        self.write(prefix)

    def gen_field(self, string):
        if self.first_field:
            self.line()
            self.push_indent()
            self.write(string)
            self.first_field = False
        else:
            self.line(",")
            self.write(string)

    def gen_args(self, obj, pa_names = False):
        """
            Given object, this method generates positional and keyword argument
        assignments for `__init__` method of object's class. Lists of arguments
        are gathered in method resolution order (MRO).
        See `get_class_total_args` for details.

            A value for assignment is searched in the object by argument name
        using built-in `getattr`. If it is not such trivial, the class must
        define `__get_init_arg_val__`. Given an argument name, it must either
        return the value or raise an `AttributeError`.

            Keyword assignment is only generated when the value differs from the
        default.  Both `is` and `==` operators are used to compare values. `is`
        is used first (optimization).

            If an `AttributeError` raised for a _keyword_ argument name, the
        argument assignment is skipped. Positional argument assignments cannot
        be skipped.

        pa_names
            whether positional arguments to be generated with names.
        """

        pal, kwal = get_class_total_args(type(obj))

        try:
            get_val = type(obj).__get_init_arg_val__
        except AttributeError:
            get_val = getattr

        for pa in pal:
            v = get_val(obj, pa)
            self.gen_field((pa + " = ") if pa_names else "")
            self.pprint(v)

        for kwa, default in kwal.items():
            try:
                v = get_val(obj, kwa)
            except AttributeError:
                # If value cannot be obtained, skip the argument generation
                continue

            # generate only arguments with non-default values
            if (v is default) or (v == default):
                continue

            self.gen_field(kwa + " = ")
            self.pprint(v)

    def gen_end(self, suffix = ")"):
        if not self.first_field:
            self.line()
            self.pop_indent()
        self.line(suffix)

        self.first_field = True

    def gen_code(self, obj, pa_names = False, suffix = ")"):
        self.reset_gen(obj)
        self.gen_args(obj, pa_names = pa_names)
        self.gen_end(suffix = suffix)

    def pprint(self, val):
        if isinstance(val, list):
            if not val:
                self.write("[]")
                return
            self.line("[")
            self.push_indent()
            if val:
                self.pprint(val[0])
                for v in val[1:]:
                    self.line(",")
                    self.pprint(v)
            self.pop_indent()
            self.line()
            self.write("]")
        elif isinstance(val, dict):
            if not val:
                self.write("{}")
                return
            self.line("{")
            self.push_indent()
            if val:
                items = sorted(val.items(), key = lambda t : t[0])

                k, v = items[0]
                self.pprint(k)
                self.write(": ")
                self.pprint(v)
                for k, v in items[1:]:
                    self.line(",")
                    self.pprint(k)
                    self.write(": ")
                    self.pprint(v)
            self.pop_indent()
            self.line()
            self.write("}")
        elif isinstance(val, tuple):
            if not val:
                self.write("()")
                return
            self.line("(")
            self.push_indent()
            if val:
                self.pprint(val[0])
                if len(val) > 1:
                    for v in list(val)[1:]:
                        self.line(",")
                        self.pprint(v)
                else:
                    self.line(",")
            self.pop_indent()
            self.line()
            self.write(")")
        elif isinstance(val, const_types):
            self.write(self.gen_const(val))
        elif val is None:
            self.write("None")
        else:
            o2n = self.obj2name
            if val in o2n:
                s = o2n[val]
            else:
                s = repr(val)
            self.write(s)

if __name__ == "__main__":
    g = PyGenerator()

    class Writer():
        def write(self, val):
            stdout.write(str(type(val)) + " : " + repr(val) + "\n")

    g.w = Writer()
