__all__ = [
    "PyGenerator"
  , "pythonize"
  , "PyGenDepsVisitor"
      , "PyGenDepsCatcher"
  , "pythonizable"
  , "pygenerate"
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
from .ordered_set import (
    OrderedSet
)


const_types = (float, text_type, binary_type, bool) + integer_types

# Those standard types are supported by `PyGenerator` without specific code.
pythonizable = const_types + (list, set, dict, tuple)


class PyGenDepsVisitor(ObjectVisitor):

    def __init__(self, root):
        super(PyGenDepsVisitor, self).__init__(root,
            field_name = "__pygen_deps__"
        )


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
        `yield` statements separate generation passes

Object serialization is performed pass by pass during `__pygen_pass__` method.
It should use the `PyGenerator` instance to output Python code.

The serialization is split into passes to support cyclic references between
objects.
The `pygen` implementation counts pass # internally for each object being
serialized.
Passes are separated by `return`s (if `__pygen_pass__` is a function) or
`yield`s (if `__pygen_pass__` is a generator).
But not every `return`/`yield` finishes the pass (see below).
If an object finished serialization, its `__pygen_pass__` method must
`return` nothing (i.e. `None`).
A generator may either `yield None` or just `return`.

Pass #0 is started unconditionally.
If other objects (dependencies) are required to complete current pass or
to begin next pass, a tuple must be `return`ed/`yield`ed.
First part of the tuple should be an iterable of the dependencies.
_The iterable can be empty if you wish to separate parts of code._
Second part should be a boolean indicator of completion of current pass.
`True` means the dependencies are for next pass and current pass finished.
The next pass begins when all dependencies finished pass of same (or greater)
number.
`False` means the pass cannot be completed right now and should continue when
all dependencies finished pass of same (or greater) number.
If an object finished its serialization, it unconditionally satisfies everyone
even if its last pass # was less.

Objects must not require each other transitively with same pass #n
(a dependency loop).
A developer is responsible to cut dependency loops onto different passes.

Normally, pass #0 generates a constructor invocation which gets references to
other objects.
Of course, pass #0 of that objects must finish before.
Hence, dependent object first `yield`s ([list of deps], False).
Its serialization will be paused until that deps all `yield` True (or
finished).
If at least one of them (or, transitively, one of its deps) yields the
dependent object, then it's a dependency loop and the serialization fails.
If there is a possibility of such a situation, a developer should do linkage
during consequent passes.
Consequent passes use implementation specific ways to setup references to
objects those constructors (or other stages of initialization process)
require reference to the current object.

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

            # preserve c's type across different Python versions
            prefix = "u" if isinstance(c, text_type) else "b"

            multiline = False
            # Double and single quote count
            dquote = 0
            squote = 0

            for ch in c:
                code = ch if isinstance(ch, int) else ord(ch)

                if code > 0xFFFF: # 4-byte unicode
                    normalized += "\\U%08x" % code
                elif code > 0xFF: # 2-byte unicode
                    normalized += "\\u%04x" % code

                # conditions above are not possible if `c` is of `binary_type`

                elif code >= 0x7F: # non-ASCII code or non-printable 0x7F (DEL)
                    normalized += "\\x%02x" % code
                elif code == 0x09: # \t
                    normalized += "\t"
                elif code == 0x0A: # \n
                    multiline = True
                    normalized += "\n"
                elif code == 0x0D: # \r
                    multiline = True
                    normalized += "\r"
                elif code < 32: # non-printable code
                    normalized += "\\x%02x" % code
                elif code == 92: # \
                    normalized += "\\\\"
                elif code == 34: # "
                    dquote += 1
                    normalized += '"'
                elif code == 38: # '
                    squote += 1
                    normalized += "'"
                else:
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

    def gen_instantiation(self, obj, **kw):
        self.write(self.nameof(obj) + " = ")

        try:
            gen_code = obj.__gen_code__
        except AttributeError:
            if isinstance(obj, pythonizable):
                self.pprint(obj)
            else:
                self.gen_code(obj, **kw)
        else:
            # deprecated API support
            gen_code(self)

        self.line()

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

    # Pythonization can be long enough.
    # Do not touch target file until it ended.
    data = pygenerate(root).w.getvalue().encode("utf-8")

    with open(path, "wb") as _file:
        _file.write(data)


EMPTY = tuple()


def pygenerate(*objs):
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
    users = dict() # id(dep) -> OrderedSet(id(user))

    # Registry of generated & skipped objects.
    # This prevents garbage collection and re-usage of ids during
    # generation.
    # Also, this is used to lookup object by id of user.
    keepalive = dict() # id(obj) -> obj

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

    # `pygen_pass` makes one pass of one `obj`ect and fills `ready` with
    # objects that can continue/begin its generation.
    # They can be handled in any order.
    # However, using stack first generates objects that became ready last.
    # `iter` is used to pause an iteration and save its state in the `stack`
    # when new objects are ready.
    # This complicated approach results in locality of big object graphs.
    # Such a layout seems more pretty to a human.
    # A straightforward approach (process objects in readiness order) results
    # in mixing of big object graphs.
    stack = deque()
    stack.append(iter(objs))
    ready = deque()

    while stack:
        i = stack[-1]

        for obj in i:
            pygen_pass(gen, generated, pass_state, deps, users, ready,
                keepalive, obj
            )
            if ready:
                stack.append(iter(ready))
                ready = deque()
                break
        else:
            stack.pop()

    if deps:
        # TODO: output dependency graph
        raise RuntimeError("Cross references")

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
                ready.append(keepalive[uid])
    else:
        next_p = p + 1

        next_pass_deps, pass_finished = pass_result
        if pass_finished:
            # pass #p of `obj` is finished, notify users
            pass_state[oid][0] = next_p
            obj_users = users[oid]
            for uid in tuple(obj_users):
                user_deps = deps[uid]

                if next_p >= user_deps[oid]:
                    del user_deps[oid]
                    obj_users.remove(uid)

                    if not user_deps:
                        del deps[uid]
                        ready.append(keepalive[uid])

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
                dep_users = users[dep_id] = OrderedSet()
                prepare_object(gen, pass_state, keepalive, dep)
            elif dep_pass_state[0] >= next_p:
                # The `dep`endency generation process is already far enough.
                continue
            else:
                dep_users = users[dep_id]

            obj_deps[dep_id] = next_p
            dep_users.add(oid)

        if obj_deps:
            deps[oid] = obj_deps
        else:
            # All dependencies of `obj` is already satisfied,
            # It can continue generation instantly.
            ready.append(obj)


def prepare_object(gen, pass_state, keepalive, obj):
    oid = id(obj)
    keepalive[oid] = obj

    try:
        gen_pass = obj.__pygen_pass__
    except AttributeError:
        pass_generator = default_gen_pass(obj, gen)
    else:
        if isgeneratorfunction(gen_pass):
            pass_generator = gen_pass(gen)
        else:
            pass_generator = gen_pass_to_coroutine(gen_pass, gen)

    pass_state[oid] = [0, pass_generator]


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

    gen.gen_instantiation(obj)


def gen_pass_to_coroutine(gen_pass, gen):
    "Converts generation function to coroutine."

    for p in count():
        res = gen_pass(gen, p)

        if res is None:
            break # generation finished

        yield res

