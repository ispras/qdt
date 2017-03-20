from common import \
    topology

from six import \
    PY2, \
    text_type, \
    integer_types

str_able_types = [bool, float] + list(integer_types)

"""
PyGenerator provides an interface for saving an object to the file.
The file is to be a python script such that execution of the file will
reconstruct the object.
"""
class PyGenerator(object):
    escape_characters = {
        "'": "\\'",
        '\\': '\\\\'
    }

    def __init__(self, indent = "    "):
        self.indent = indent

        self.reset()

    def escape(self, val):
        for k, v in self.escape_characters.items():
            val = val.replace(k, v)
        return val

    def reset(self):
        self.obj2name = {}
        self.current_indent = ""
        self.max_name = 0
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
            name = "obj%u" % self.max_name
            self.max_name = self.max_name + 1
            self.obj2name[obj] = name

        return self.obj2name[obj]

    def serialize(self, writer, root):
        self.w = writer
        self.reset()

        objects = topology.sort_topologically([root])

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
        if isinstance(c, bool):
            return "True" if c else "False"
        elif isinstance(c, integer_types):
            if c <= 0:
                return "%d" % c
            else:
                return "0x%0x" % c
        elif isinstance(c, str):
            return "\"" + c + "\""
        elif isinstance(c, bool):
            return "True" if c else "False"
        else:
            return str(c)

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

    def gen_end(self, suffix = ")"):
        if not self.first_field:
            self.line()
            self.pop_indent()
        self.line(suffix)

        self.first_field = True

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
                k, v = list(val.items())[0]
                self.pprint(k)
                self.write(": ")
                self.pprint(v)
                for k, v in list(val.items())[1:]:
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
        elif type(val) in str_able_types:
            self.write(str(val))
        elif PY2 and isinstance(val, str):
            val = self.escape(val)
            self.write("'" + val + "'")
        elif isinstance(val, text_type):
            val = self.escape(val)
            self.write("u'" + val + "'")
        elif val is None:
            self.write("None")
        else:
            self.write(self.obj2name[val])
