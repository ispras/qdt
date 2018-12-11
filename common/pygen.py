__all__ = [
    "PyGenerator"
  , "pythonize"
  , "PyGenVisitor"
]

from six import (
    StringIO,
    text_type,
    binary_type,
    integer_types
)
from itertools import (
    count
)
from .code_writer import (
    CodeWriter
)
from .reflection import (
    get_class_total_args
)
from .visitor import (
    BreakVisiting,
    ObjectVisitor
)

const_types = (float, text_type, binary_type, bool) + integer_types

not_generated = 0
generating = 1
generated = 2

class PyGenVisitor(ObjectVisitor):

    def __init__(self, root, backend = None, **genkw):
        super(PyGenVisitor, self).__init__(root,
            field_name = "__pygen_deps__"
        )

        if backend is None:
            backend = StringIO()

        self.gen = PyGenerator(backend = backend, **genkw)

    def on_visit(self):
        oid = id(self.cur)
        state = self.state.get(oid, not_generated)

        if state is generating:
            raise RuntimeError("Recursive dependencies")

        if state is generated:
            raise BreakVisiting()

        self.state[oid] = generating

    def on_leave(self):
        o = self.cur
        oid = id(o)

        # prevent garbage collection
        self.keepalive.append(o)

        if self.state[oid] is generating:
            self.state[oid] = generated
        else:
            return

        try:
            gen_code = o.__gen_code__
        except AttributeError:
            return

        g = self.gen

        g.write(g.nameof(o) + " = ")
        gen_code(g)
        g.line()

    def visit(self):
        self.gen.reset()

        self.state = {}
        # List of generated & skipped objects.
        # This prevents garbage collection and re-usage of ids during
        # generation.
        # It can happen when the value of an attribute listed in
        # `__pygen_deps__` is generated dynamically using [non-]data
        # descriptor like `property`.
        self.keepalive = []

        ret = super(PyGenVisitor, self).visit()

        # generate root
        o = self.cur

        if id(o) not in self.state:
            g = self.gen
            g.write(g.nameof(o) + " = ")

            try:
                gen_code = o.__gen_code__
            except AttributeError:
                g.pprint(o)
            else:
                gen_code(g)

            g.line()

        return ret


class PyGenerator(CodeWriter):
    """ PyGenerator provides an API for serialization of objects in a Python
script.

    Each object must have:

    - __gen_code__, a method that is given a `PyGenerator` instance. It should
        use the instance to write Python code that is equivalent to the object.

    - __dfs_children__, a method that is used by `PyGenerator` to locate
        objects this object does depend on.
        See `common.topology.sort_topologically` for details.

    An object may have:

    - __var_base__, a method that must return a string which will be used by
        `PyGenerator` to evaluate name for the variable generated for the
        object.

    - __get_init_arg_val__, a method to transform values of arguments before
        serialization to Python. See `PyGenerator.gen_args`.

    The goal is to produce a script, execution of which will result in a set
of objects those are equivalent to original objects. However, `PyGenerator`
only provides useful methods for it. Actual equivalence depends on user's
accuracy.
    """

    def reset(self):
        super(PyGenerator, self).reset()

        self.id2name = {}
        self.name2obj = {}
        self.name_counter = {}

    def nameof(self, obj):
        if obj is None:
            return "None"

        obj_id = id(obj)

        if obj_id not in self.id2name:
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

            self.id2name[obj_id] = name
            self.name2obj[name] = obj

        return self.id2name[obj_id]

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

    def pprint_list(self, val):
        self.line("[")
        self.push_indent()
        self.pprint(val[0])
        for v in val[1:]:
            self.line(",")
            self.pprint(v)
        self.pop_indent()
        self.line()
        self.write("]")

    def pprint(self, val):
        if isinstance(val, list):
            if type(val) is not list:
                self.write(type(val).__name__ + "(")
            if not val:
                self.write("[]")
            else:
                self.pprint_list(val)
            if type(val) is not list:
                self.write(")")
        elif isinstance(val, set):
            if not val:
                self.write("set([])")
                return
            self.write("set(")
            self.pprint_list(sorted(val))
            self.write(")")
        elif isinstance(val, dict):
            if type(val) is not dict:
                self.write(type(val).__name__ + "(")
            if not val:
                self.write("{}")
            else:
                self.line("{")
                self.push_indent()

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
            if type(val) is not dict:
                self.write(")")
        elif isinstance(val, tuple):
            if not val:
                self.write("()")
                return
            self.line("(")
            self.push_indent()
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
            o2n = self.id2name
            val_id = id(val)
            if val_id in o2n:
                s = o2n[val_id]
            else:
                s = repr(val)
            self.write(s)


def pythonize(root, path):
    """ Serializes graph of objects presented by its :root: object to Python
    script and writes it to file. See `PyGenerator`.

    :obj: to be serialized
    :path: of target file
    """

    res = PyGenVisitor(root).visit().gen.w

    with open(path, "wb") as _file:
        _file.write(res.getvalue().encode("utf-8"))

