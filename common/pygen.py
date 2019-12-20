__all__ = [
    "PyGenerator"
  , "pythonize"
  , "PyGenDepsVisitor"
      , "PyGenVisitor"
      , "PyGenDepsCatcher"
  , "pythonizable"
  , "pygenerate"
  , "pygen"
  , "gen_code_common"
]

from six import (
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
from collections import (
    deque
)
from inspect import (
    isgeneratorfunction
)


const_types = (float, text_type, binary_type, bool) + integer_types

# Those standard types are supported by `PyGenerator` without specific code.
pythonizable = const_types + (list, set, dict, tuple)

NOT_GENERATED = 0
GENERATING = 1
GENERATED = 2


class PyGenDepsVisitor(ObjectVisitor):

    def __init__(self, root):
        super(PyGenDepsVisitor, self).__init__(root,
            field_name = "__pygen_deps__"
        )


class PyGenVisitor(PyGenDepsVisitor):

    def __init__(self, root, backend = None, **genkw):
        super(PyGenVisitor, self).__init__(root)

        self.gen = PyGenerator(backend = backend, **genkw)

    def on_visit(self):
        oid = id(self.cur)
        state = self.state.get(oid, NOT_GENERATED)

        if state is GENERATING:
            raise RuntimeError("Recursive dependencies")

        if state is GENERATED:
            raise BreakVisiting()

        self.state[oid] = GENERATING

    def on_leave(self):
        o = self.cur
        oid = id(o)

        # prevent garbage collection
        self.keepalive.append(o)

        if self.state[oid] is GENERATING:
            self.state[oid] = GENERATED
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
            gen_code_common(o, self.gen)

        return ret


class PyGenerator(CodeWriter):
    """ PyGenerator provides an API for serialization of objects in a Python
script.

    The goal is to produce a script, execution of which will result in a set
of objects those are equivalent to original objects. However, `PyGenerator`
only provides useful methods for it. Actual equivalence depends on user's
accuracy.

    Each object must have:

    - __pygen_pass__, a method that is given a `PyGenerator` instance and
        current pass number >= 0 (see below)

    or

    - __pygen_pass__, a generator that is given a `PyGenerator` instance and
        `yield` states separates generation passes

Object serialization is performed pass by pass using `__pygen_pass__` method.
It uses the `PyGenerator` instance to output Python code.
Pass #0 is performed unconditionally.
If an object finished serialization, it `return`s nothing (i.e. `None`).
A generator may `yield None` instead.
If it requires other objects (dependencies) to be generated before its next
pass started, it must `return` / `yield` an interable of the dependencies.
_The iterable can be empty but why to split generation without a reason?_
A dependency is satisfied when either its pass #n became greater than
pass #n of the dependent object or the dependency generation finished.
I.e. dependent object waits until all dependencies run ahead it.
Objects must not require each other transitively with same pass #n
(a dependency loop).
A developer is responsible to cut dependency loops onto different passes.

    An object may have:

    - __var_base__, a method that must return a string which will be used by
        `PyGenerator` to evaluate name for the variable generated for the
        object.

    - __get_init_arg_val__, a method to transform values of arguments before
        serialization to Python. See `PyGenerator.gen_args`.

    (deprecated API) Each object must have:

    - __gen_code__, a method that is given a `PyGenerator` instance. It should
        use the instance to write Python code that is equivalent to the object.

    - __pygen_deps__, an attribute that is used by `PyGenerator` to locate
        objects this object does depend on. It must list names of
        corresponding attributes. See `ObjectVisitor.field_name` description.
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

    @staticmethod
    def gen_const(c):
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

    def gen_args(self, obj, pa_names = False, skip_kw = []):
        """
            Given object, this method generates positional and keyword argument
        assignments for `__init__` method of object's class. Lists of arguments
        are gathered in method resolution order (MRO).
        See `get_class_total_args` for details.
        Warning! It fails if `__init__` has been replaced. E.g. by a class
        decorator.

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

    :param pa_names:
        whether positional arguments to be generated with names.

    :param skip_kw:
        keyword arguments to be skipped (list, set or tuple)
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
            if kwa in skip_kw:
                continue

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
                self.write(type(val).__name__ + "()")
            else:
                self.write(type(val).__name__ + "(")
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
            if type(val) is not tuple:
                # Unlike another containers, a `tuple` subclass is expected to
                # override `__new__` to get fixed number of arguments instead
                # of building itself from another `tuple` (its subclass) as
                # one argument. `collections.namedtuple` is an example.
                # So, just add name of the subclass before the parentheses.
                self.write(type(val).__name__)
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

    with open(path, "wb") as _file:
        _file.write(pygenerate(root).w.getvalue().encode("utf-8"))


def pygenerate(root):
    return pygen([root])


EMPTY = tuple()


def pygen(objs):
    # See `PyGenerator` for general algorithm description.

    gen = PyGenerator()
    gen.reset()

    if not objs:
        return gen

    # pass_state[id(obj)]:
    # [0] == [# of last passed pass of obj] - 1
    # [1] is a coroutine that performs passes yielding dependencies for
    #     next pass.
    pass_state = {}

    # Dependencies between generation passes of objects.
    deps = dict() # id(user) -> dict(id(dep) -> required dep's pass #)
    users = dict() # id(dep) -> dict(id(user) -> user)

    # List of generated & skipped objects.
    # This prevents garbage collection and re-usage of ids during
    # generation.
    keepalive = []

    generated = set()

    for obj in objs:
        oid = id(obj)
        if oid in pass_state:
            # duplicating reference
            continue

        prepare_object(gen, pass_state, keepalive, obj)

        # When obj's generation finished, dependent objects become ready.
        # But there is no dependent object for starting objects.
        users[oid] = EMPTY

    while True:
        ready = deque()

        for obj in objs:
            pygen_pass(gen, generated, pass_state, deps, users, ready,
                keepalive, obj
            )

        if not ready:
            if deps:
                # TODO: output dependency graph
                raise RuntimeError("Cross references")
            break

        objs = ready

    return gen


def pygen_pass(gen, generated, pass_state, deps, users, ready, keepalive, obj):
    oid = id(obj)

    # assert oid not in generated, "%s" % obj
    # assert oid not in deps, "%s" % obj

    p, pass_generator = pass_state[oid]

    try:
        pass_result = next(pass_generator)
    except StopIteration:
        pass_result = None

    if pass_result is None:
        generated.add(oid)

        # No more passes will be for `obj`.
        # All its users are satisfied unconditionally.
        obj_users = users.pop(oid)
        for uid in obj_users:
            user_deps = deps[uid]
            del user_deps[oid]

            if not user_deps:
                # This was last dependency of user.
                # It's now ready for next pass.
                del deps[uid]
                ready.append(obj_users[uid])
    else:
        next_p = p + 1

        next_pass_deps, pass_finished = pass_result
        if pass_finished:
            deps_p = next_p
            # pass #p of `obj` is finished, notify users
            pass_state[oid][0] = next_p
            obj_users = users[oid]
            for uid in tuple(obj_users):
                user_deps = deps[uid]

                if next_p >= user_deps[oid]:
                    del user_deps[oid]

                    if user_deps:
                        del obj_users[uid]
                    else:
                        del deps[uid]
                        ready.append(obj_users.pop(uid))
        else:
            deps_p = next_p

        # handle dependencies
        obj_deps = {}
        for dep in next_pass_deps:
            dep_id = id(dep)

            if dep_id in generated:
                continue

            dep_pass_state = pass_state.get(dep_id, None)

            if dep_pass_state is None:
                # new object
                ready.append(dep)
                dep_users = users[dep_id] = dict()
                prepare_object(gen, pass_state, keepalive, dep)
            elif dep_pass_state[0] >= deps_p:
                # The `dep`endency generation process is already far enough.
                continue
            else:
                dep_users = users[dep_id]

            obj_deps[dep_id] = deps_p
            dep_users[oid] = obj

        if obj_deps:
            deps[oid] = obj_deps
        else:
            # All dependencies of `obj` is already satisfied,
            # It can continue generation instantly.
            ready.append(obj)


def prepare_object(gen, pass_state, keepalive, obj):
    keepalive.append(obj)

    try:
        gen_pass = obj.__pygen_pass__
    except AttributeError:
        pass_generator = default_gen_pass(obj, gen)
    else:
        if isgeneratorfunction(gen_pass):
            pass_generator = gen_pass(gen)
        else:
            pass_generator = gen_pass_to_coroutine(gen_pass, gen)

    pass_state[id(obj)] = [0, pass_generator]


class PyGenDepsCatcher(PyGenDepsVisitor):
    "Gets dependencies according to deprecated `PyGenerator` API."

    def __init__(self, root):
        super(PyGenDepsCatcher, self).__init__(root)
        self.deps = []

    def on_visit(self):
        cur = self.cur
        if hasattr(cur, "__gen_code__") or hasattr(cur, "__pygen_pass__"):
            self.deps.append(cur)
            raise BreakVisiting()


def default_gen_pass(obj, gen):
    # deprecated API support
    deps = PyGenDepsCatcher(obj).visit().deps

    if deps:
        yield deps, False

    gen_code_common(obj, gen)


def gen_pass_to_coroutine(gen_pass, gen):
    "Converts generation function to coroutine."

    for p in count():
        res = gen_pass(gen, p)

        if res is None:
            break # generation finished

        yield res


def gen_code_common(obj, gen):
    gen.write(gen.nameof(obj) + " = ")

    try:
        gen_code = obj.__gen_code__
    except AttributeError:
        gen.pprint(obj)
    else:
        # deprecated API support
        gen_code(gen)

    gen.line()
