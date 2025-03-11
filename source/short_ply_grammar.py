""" Helpers to shortening of PLY grammars
"""

__all__ = [
    "short_ply_rule"
  , "short_ply_grammar"
]

from common.compat import (
    getargspec,
)
from common.ply_tools import (
    iter_class_tokens,
)
from common.pypath import (
    pypath,
)

with pypath("..ply"):
    from ply.yacc import (
        yacc
    )
    from ply.lex import (
        lex
    )


def short_ply_rule(p_func, is_method = None):
    """A decorator to make short form of production handling function
suitable for PLY's yacc.
    """
    name = p_func.__name__

    if name[:2] != "p_":
        name = "p_" + name

    prod_name = name.split("__")[0][2:]

    args = getargspec(p_func)[0]

    if is_method is None:
        is_method = (args and (args[0] == "self"))

    if is_method:
        parts = args[1:]
    else:
        parts = args

    parts = list(n.split("__")[0] for n in parts)

    parts_n = len(parts)

    if is_method:
        def p_prod(self, p):
            p[0] = p_func(self, *p[1:(parts_n + 1)])
    else:
        def p_prod(p):
            p[0] = p_func(*p[1:(parts_n + 1)])

    rule = prod_name + " : " + " ".join(parts)

    ns = dict(
        p_prod = p_prod,
    )

    line = getattr(p_func, "co_firstlineno", p_func.__code__.co_firstlineno)

    # PLY's yacc accounts rule's line number which is line number of the
    # function defining that rule.

    code = "\n" * (line - 2) + """
def {name}({args}):
    "{rule}"
    p_prod({args})
""".format(
    name = name,
    rule = rule,
    args = ", ".join(getargspec(p_prod)[0])
)

    exec(code, ns)

    wrp = ns[name]

    # for PLY's `ParserReflect.validate_pfunctions`
    if wrp.__module__ is None:
        wrp.__module__ = p_func.__module__

    return wrp


def short_ply_grammar(*a, **kw):
    if kw or not a or not isinstance(a[0], type):
        return lambda cls : _short_ply_grammar(cls, *a, **kw)
    else:
        return _short_ply_grammar(cls)


def _short_ply_grammar(cls,
    optimize = True,
    lextab = None,
    parsetab = None,
    debugfile = None,
    start = None,
):
    if lextab is None:
        lextab = "_" + cls.__name__ + "_lextab"

    if parsetab is None:
        parsetab = "_" + cls.__name__ + "_parsetab"

    if debugfile is True:
        debugfile = "_" + cls.__name__ + "_yacc_debug.txt"

    cls.tokens = tuple(iter_class_tokens(cls))

    cls.lexer = lex(
        object = cls,
        optimize = optimize,
        lextab = lextab,
    )

    for attr in dir(cls):
        if not attr.startswith("p_"):
            continue
        if attr == "p_error":
            continue

        setattr(cls, attr, short_ply_rule(getattr(cls, attr)))

    cls.parser = yacc(
        module = cls,
        tabmodule = parsetab,
        debugfile = debugfile,
        debug = bool(debugfile),
        start = start,
    )

    @classmethod
    def parse(cls, *a, **kw):
        kw["lexer"] = cls.lexer.clone()
        return cls.parser.parse(*a, **kw)

    cls.parse = parse

    return cls
