from six import \
    PY2, \
    text_type, \
    binary_type, \
    integer_types

if __name__ == "__main__":
    from topology import \
        sort_topologically

    from reflection import \
        get_class_total_args
else:
    from .topology import \
        sort_topologically

    from .reflection import \
        get_class_total_args

str_able_types = (float,) + integer_types

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
        if isinstance(c, bool):
            return "True" if c else "False"
        elif isinstance(c, integer_types):
            if c <= 0:
                return "%d" % c
            else:
                return "0x%0x" % c
        elif isinstance(c, (binary_type, text_type)):
            normalized = ""
            prefix = ""
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
                    normalized += chr(code)

            if dquote > squote:
                escaped = normalized.replace("'", "\\'")
                return prefix + "'" + escaped + "'"
            else:
                escaped = normalized.replace('"', '\\"')
                return prefix + '"' + escaped + '"'
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

    def pprint_text(self, text):
        # Double and single quote count
        dquote = 0
        squote = 0

        text_utf8 = text_type('')

        for c in text:
            if c == '"':
                dquote += 1
            elif c == "'":
                squote += 1
            elif c == "\\":
                c = "\\\\"

            text_utf8 += text_type(c)

        if dquote > squote:
            escaped = text_utf8.replace(u"'", u"\\'")
            self.write(u"u'" + escaped + u"'")
        else:
            escaped = text_utf8.replace(u'"', u'\\"')
            self.write(u'u"' + escaped + u'"')

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
        elif isinstance(val, bool):
            self.write("True" if val else "False")
        elif isinstance(val, str_able_types):
            self.write(str(val))
        elif (PY2 and isinstance(val, str)) or isinstance(val, text_type):
            self.pprint_text(val)
        elif val is None:
            self.write("None")
        else:
            self.write(self.obj2name[val])

if __name__ == "__main__":
    from sys import stdout

    g = PyGenerator()

    class Writer():
        def write(self, val):
            stdout.write(str(type(val)) + " : " + repr(val) + "\n")

    g.w = Writer()

    g.pprint_text("String in default encoding")
    g.line()
    g.pprint_text(u"Unicode string")
    g.line()
    g.pprint_text(b"ASCII string")
    g.line()
