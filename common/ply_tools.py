__all__ = [
    "gen_tokens"
  , "def_tokens"
  , "iter_rules"
  , "unify_rules"
  , "join_tokens"
  , "make_count_columns"
  , "autoname_rule"
]

from types import (
    FunctionType,
    MethodType
)
from .pypath import (
    pypath
)
from inspect import (
    currentframe,
    getframeinfo
)
with pypath("..ply"):
    from ply.helpers import (
        iter_tokens
    )
from re import (
    compile
)


def gen_tokens(glob):
    "Given global scope yielding PLY tokens."
    for g in list(glob):
        if g.startswith("t_"):
            name = g[2:]
            if name in ("error", "ignore"):
                continue
            yield name

def def_tokens(glob):
    glob["tokens"] = tuple(gen_tokens(glob))

def iter_rules(glob):
    for k, v in tuple(glob.items()):
        if not k.startswith("p_") or k == "p_error":
            continue
        if isinstance(v, (FunctionType, MethodType)):
            yield k, v

re_autoname_rule = compile(r"\s*:.*")

def autoname_rule(p_func):
    """ Append rule name before ":" if required.
Rule name is p_func's name without "p_".
    """
    rule = p_func.__doc__
    if re_autoname_rule.match(rule):
        rule = p_func.__name__[2:] + " " + rule
    return rule

def _unify_rule(p_func, globs_before):
    line = getattr(p_func, "co_firstlineno", p_func.__code__.co_firstlineno)
    # PLY's yacc accounts rule's line number which is line number of the
    # function defining that rule.
    code = "\n" * (line - 1) + """\
def _{p_func}(p):
    \"""{rule}\"""
    {p_func}(p)
    p[0] = p.slice[1:]
""".format(
        p_func = p_func.__name__,
        rule = autoname_rule(p_func)
    )
    exec(code, globs_before)

def unify_rules(glob, unifier = _unify_rule):
    """ This helper calls `unifier` for each rule function. It is given
the function and snapshot (dict) of global name space, and must define a
functions with name (`_` + {name of given function}) inside the snapshot.
That new function will replace the first one inside real global name space.

    By default, the unifier defines a function that calls the original one
and also sets value of `YaccSymbol` as list of (non-)terminals reduced
according to the rule. It result in a full parsing tree.
    """
    glob_snapshot = dict(glob)
    for k, v in tuple(iter_rules(glob_snapshot)):
        unifier(v, glob_snapshot)

        glob[k] = glob_snapshot["_" + k]

def make_count_columns(glob, line_shift = 0):
    """ Given string-defined PLY tokens (in globa) converts them into
function-defined tokens which counts columns. A user must initialize
`columnno` attribute to 1 (recommended value) of lexer by self.

Call this function after all function-defined tokens. If you want to add
function-defined tokens after, then play with `line_shift`. It is probably
should point to line of first string-defined token relative to this function
call. It's also not recommended to mix function- & string-defined tokens.
    """

    # It defines functions from `str`ing constants. The constants are assigned
    # lowest priority by PLY. But, function priority is based on its line
    # number. However, the priority must remain lowest. So, created functions
    # are assigned line number of this function call..
    line = getframeinfo(currentframe().f_back).lineno

    # Also, PLY does assign highest priority to longest regular expressions.
    # We should preserve this by adding extra line numbers.
    for i, (n, v) in enumerate(
        sorted(
            filter(lambda p: isinstance(p[1], str),
                   dict(glob).items()
            ),
            key = lambda p: -len(p[1])
        ),
        line_shift
    ):
        if n.startswith("t_"):
            code =  "\n" * (line - 1 + i) + """
def {tok}(t):
    r"{regexp}"
    t.lexer.columnno += len(t.value)
    return t
            """.format(
    tok = n,
    regexp = v
            )
            exec(code, glob)

def join_tokens(root):
    res = ""
    for t in iter_tokens(root):
        res += t.value
    return res
