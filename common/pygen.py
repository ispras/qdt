from common import topology

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
            self.w.write(self.current_indent)
        else:
            self.new_line = True

        self.w.write(suffix + "\n")

    def write(self, string = ""):
        if self.new_line:
            self.w.write(self.current_indent)
            self.new_line = False

        self.w.write(string)

    def push_indent(self):
        self.current_indent = self.current_indent + self.indent

    def pop_indent(self):
        self.current_indent = self.current_indent[:-len(self.indent)]

    def nameof(self, obj):
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
                o.__gen_code__(self)
            except Exception, e:
                print e
                self.line("None")
            self.line()

    def gen_const(self, c):
        if isinstance(c, bool):
            return "True" if c else "False"
        elif isinstance(c, int) or isinstance(c, long):
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
