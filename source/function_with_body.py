__all__ = [
    "function_with_body"
  , "ReturnTypeFinder"
]


from common import (
    getargspec,
    StopVisiting,
)
from .function.bindings import (
    BodyTree,
)
from .function.tree import (
    Return,
)
from .late import (
    Late,
)
from .model import (
    Function,
    NodeVisitor,
    Type,
    TypeNotRegistered,
)

from itertools import (
    zip_longest,
)


def function_with_body(gen):
    """ Given a function body tree `gen`erator function, the function
returns `Function` instance with generated body.
`__name__` is same.
Argument types must be given as default values.
`static` and `inline` argument values are passed to `Function`.
`ret_type` is determined automatically but can be given explicitly too.
The `gen`erator is started is course of the `Function` instantiation and is
given argument `Variables` as values to corresponding arguments.
So, the could be used in course of body tree generation.
    """
    name = gen.__name__
    args, varargs, varkw, defaults = getargspec(gen)

    if varargs is not None or varkw is not None:
        raise ValueError(
"%s: `Function`'s `BodyTree` generator must not have *args or **kw" % name
        )

    argtypes = []
    notypes = []

    func_args = dict(
        static = None,
        inline = None,
        ret_type = None,
    )

    for aname, atype in zip_longest(reversed(args), reversed(defaults)):
        if aname in func_args:
            func_args[aname] = atype
            continue
        if atype is None:
            notypes.append(aname)
        else:
            argtypes.insert(0, (aname, atype))

    if notypes:
        raise ValueError(
            "%s: argument(s) %s have no type specified" % (
                name, ", ".join(notypes)
            )
        )

    argvars = []

    for aname, atype_name in argtypes:
        if isinstance(atype_name, Type):
            atype = atype_name
        else:
            try:
                atype = Type[atype_name]
            except TypeNotRegistered:
                atype = Late(atype_name)
        argvars.append(atype(aname))

    body = BodyTree()
    # Because some args are handled spefically, arg positions may not match.
    # Pass values with explicit names.
    body(*gen(**dict((a.name, a) for a in argvars)))

    if "ret_type" not in func_args:
        func_args["ret_type"] = ReturnTypeFinder(body).visit().ret_type

    func = Function(
        name = name,
        args = argvars,
        body = body,
        **dict(kv for kv in func_args.items() if kv[1] is not None)
    )

    return func


class ReturnTypeFinder(NodeVisitor):

    def __init__(self, *a, **kw):
        super(ReturnTypeFinder, self).__init__(*a, **kw)
        self.in_return = False
        self.ret_type = None

    def __visit__(self, o):
        if isinstance(o, Return):
            assert not self.in_return, "`return` inside `return`?"
            self.in_return = True

        if not self.in_return:
            return

        # rely on `Node`'s `type` `@property`
        t = o.type
        if t is not None:
            self.ret_type = t
            raise StopVisiting

    def __leave__(self, o):
        if isinstance(o, Return):
            assert self.in_return
            self.in_return = False
