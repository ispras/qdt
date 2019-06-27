__all__ = [
    "ctags_lexer"
  , "ctags_parser"
]

from common import (
    lazy,
    def_tokens,
    unify_rules
)
from .generic import (
    INode,
    inodify_rule
)
from ply.lex import (
    lex
)
from ply.yacc import (
    yacc
)


def t_PAIR_ITEM(t):
    r"[^\t\n:]+"
    return t


t_NL = r"\n"
t_COLON = ":"

t_ignore = "\t"

def_tokens(globals())


def t_error(t):
    raise ValueError("Unexpected character in ctags: " + repr(t.value[0]))


ctags_lexer = lex()


def p_ctags(p):
    """ ctags : line
              | ctags line
    """
    return CTags


def p_line(p):
    "line : field field field extension_fields NL"
    return Tag


# fields may have colons inside
def p_field(p):
    """ field : PAIR_ITEM
              | field COLON PAIR_ITEM
    """
    return Field


def p_extension_fields(p):
    """ extension_fields : pair
                         | extension_fields pair
    """
    return Fields


def p_pair(p):
    "pair : PAIR_ITEM COLON PAIR_ITEM"
    p.slice[1].tags = ["id"]
    p.slice[3].tags = ["string"]


unify_rules(globals(), unifier = inodify_rule)


def p_error(p):
    raise ValueError("Unknown ctags syntax")


class CTags(INode):

    def iter_tags(self):
        for rsubtree in self.lr_iter("ctags"):
            yield rsubtree[0].value

    @lazy
    def tags(self):
        return tuple(self.iter_tags())


class Tag(INode):

    @lazy
    def name(self):
        return self[0].value.value

    @lazy
    def file_name(self):
        return self[1].value.value

    @lazy
    def ex_cmd(self):
        return self[2].value.value

    @lazy
    def fields(self):
        return self[3].value

    def __getattr__(self, name):
        "Cached access to fields"

        val = self.fields[name]
        self.__dict__[name] = val
        return val

    def __str__(self):
        return self.name + "\n  " + "\n  ".join(
            ("%s : %s" % p) for p in self.fields.pairs
        )


class Field(INode):

    @lazy
    def value(self):
        res = ""
        for rsubtree in self.lr_iter("field"):
            for tok in rsubtree:
                res += tok.value
        return res


class Fields(INode):

    def iter_pairs(self):
        for rsubtree in self.lr_iter("extension_fields"):
            pair = rsubtree[0].value
            key, value = pair[0].value, pair[2].value
            yield key, value

    @lazy
    def pairs(self):
        return tuple(self.iter_pairs())

    @property
    def dict(self):
        return dict(self.pairs)

    @lazy
    def _dict(self): # private copy, do not change it
        return self.dict

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._dict[key]
        # integer / slice access must not be overriden
        return super(Fields, self).__getitem__(key)


ctags_parser = yacc(write_tables = False)
