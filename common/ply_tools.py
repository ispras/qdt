__all__ = [
    "gen_tokens"
  , "def_tokens"
  , "iter_rules"
  , "unify_rules"
  , "make_count_columns"
]

from types import (
    FunctionType,
    MethodType
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
        rule = p_func.__doc__
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

def make_count_columns(glob):
    """ Makes PLY token functions to count column. A user must initialize
`columnno` attribute to 1 (recommended value) of lexer by self.
    """

    for n, v in dict(glob).items():
        if isinstance(v, str) and n.startswith("t_"):
            code = """
def {tok}(t):
    r"{regexp}"
    t.lexer.columnno += len(t.value)
    return t
            """.format(
    tok = n,
    regexp = v
            )
            exec(code, glob)
