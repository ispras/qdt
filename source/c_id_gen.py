__all__ = [
    "CIdGen"
]

from .short_ply_grammar import (
    short_ply_grammar,
)

from six.moves import (
    zip,
)
from collections import (
    namedtuple as nt
)

# Different character forms are used for generation of different entities.
# I.e. name of function or variable must use lower case. A MACRO must use
# upper case. A structure must have upper camel case name.
cidchar = nt("cidchar", "id_char file_char struct_char macro_char")
cid = nt("cid", "id file struct macro")

@short_ply_grammar()
class CIdGen(object):

    # Allowed characters.

    @staticmethod
    def t_NUMBER(t):
        r"[0-9]+"
        c = t.value
        t.value = cidchar(c, c, c, c)
        return t

    @staticmethod
    def t_LOWER(t):
        r"[a-z]"
        c = t.value
        t.value = cidchar(c, c, c, c.upper())
        return t

    @staticmethod
    def t_UPPER(t):
        r"[A-Z]"
        c = t.value
        t.value = cidchar(c.lower(), c.lower(), c, c)
        return t

    # Special replacements for forbidden characters.

    # Slash is just discarded.
    # Ex.: "I/O" ("Input/Output") should be handled as IO, etc.
    @staticmethod
    def t_SLASH(t):
        r"[/\\]"

    # Replace forbidden characters with '_'.
    # But `struct` name must not have `_`.
    @staticmethod
    def t_FORBIDDEN(t):
        r"."
        t.value = cidchar('_', '_', '', '_')
        return t

    @staticmethod
    def t_error(t):
        raise NotImplementedError(
            "You just found a bug in Qemu type name generator!"
        )

    # Parser produces list of `qtnchar`s those will be used for thing
    # construction.

    @staticmethod
    def p_stripped__empty_or_forbidden_only(prefix):
        return [cidchar("", "", "", "")]

    @staticmethod
    def p_stripped__left(prefix, partial):
        # Prefix discards unused junk.
        return partial

    @staticmethod
    def p_prefix():
        pass

    @staticmethod
    def p_prefix__discard_leading_digits(prefix, NUMBER):
        return prefix

    @staticmethod
    def p_prefix__discard_leading_separators(prefix, separator):
        return prefix

    @staticmethod
    def p_stripped__right(prefix, head):
        # Discard separator to the right.
        # Note, multiple separators are discarded by `head` rule.
        return head[:-1]

    @staticmethod
    def p_partial(word):
        return word

    @staticmethod
    def p_partial__concat(partial, word):
        return partial + word

    @staticmethod
    def p_head(partial, separator):
        return partial + separator

    @staticmethod
    def p_head__2(head, separator):
        # Take only first separator, discard rest.
        return head

    @staticmethod
    def p_partial__join_digits(head, digits):
        return head + digits

    @staticmethod
    def p_partial__join_word(head, word):
        # Capitalize structure name.
        return head + [
            word[0]._replace(struct_char = word[0].struct_char.capitalize())
        ] + word[1:]

    @staticmethod
    def p_word__LOWER(LOWER):
        return [LOWER]

    @staticmethod
    def p_word__UPPER(UPPER):
        return [UPPER]

    @staticmethod
    def p_word__digits(word, digits):
        return word + digits

    @staticmethod
    def p_separator__SLASH(SLASH):
        return [SLASH]

    @staticmethod
    def p_separator__FORBIDDEN(FORBIDDEN):
        return [FORBIDDEN]

    # numbers may be separated by an ignored token (like SLASH)
    @staticmethod
    def p_digits__join(digits, NUMBER):
        return digits + [NUMBER]

    @staticmethod
    def p_digits(NUMBER):
        return [NUMBER]

    p_error = t_error

    @classmethod
    def generate(cls, raw, *parse_args, **parse_kw):
        result = cls.parse(raw, *parse_args, **parse_kw)
        return cid(*map("".join, zip(*result)))
