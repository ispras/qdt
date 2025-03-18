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

    def t_NUMBER(t):
        r"[0-9]+"
        c = t.value
        t.value = cidchar(c, c, c, c)
        return t

    def t_LOWER(t):
        r"[a-z]"
        c = t.value
        t.value = cidchar(c, c, c, c.upper())
        return t

    def t_UPPER(t):
        r"[A-Z]"
        c = t.value
        t.value = cidchar(c.lower(), c.lower(), c, c)
        return t

    # Special replacements for forbidden characters.

    # Slash is just discarded.
    # Ex.: "I/O" ("Input/Output") should be handled as IO, etc.
    def t_SLASH(t):
        r"[/\\]"

    # Replace forbidden characters with '_'.
    # But `struct` name must not have `_`.
    def t_FORBIDDEN(t):
        r"."
        t.value = cidchar('_', '_', '', '_')
        return t

    def t_error(t):
        raise NotImplementedError(
            "You just found a bug in Qemu type name generator!"
        )

    # Parser produces list of `cidchar`s those will be used for thing
    # construction.

    def p_stripped__empty_or_forbidden_only(prefix):
        return [cidchar("", "", "", "")]

    def p_stripped__left(prefix, partial):
        # Prefix discards unused junk.
        return partial

    def p_stripped__right(prefix, head):
        # Discard separators to the right.
        # Note, multiple separators are discarded by `head` rule.
        return head[:-1]

    def p_prefix():
        pass

    def p_prefix__discard_leading_digits(prefix, NUMBER):
        return prefix

    def p_prefix__discard_leading_separators(prefix, separators):
        return prefix

    def p_head(partial, separators):
        # Take only first separator, discard rest.
        return partial + separators[:1]

    def p_partial(word):
        return word

    def p_partial__join_digits(head, digits):
        return head + digits

    def p_partial__join_word(head, word):
        # Capitalize structure name.
        return head + [
            word[0]._replace(struct_char = word[0].struct_char.capitalize())
        ] + word[1:]

    def p_partial__concat(partial, word):
        return partial + word

    def p_word__LOWER(LOWER):
        return [LOWER]

    def p_word__UPPER(UPPER):
        return [UPPER]

    def p_word__digits(word, digits):
        return word + digits

    def p_separators(separators__0, separators__1):
        return separators__0 + separators__1

    def p_separators__SLASH(SLASH):
        return [SLASH]

    def p_separators__FORBIDDEN(FORBIDDEN):
        return [FORBIDDEN]

    # numbers may be separated by an ignored token (like SLASH)
    def p_digits__join(digits, NUMBER):
        return digits + [NUMBER]

    def p_digits(NUMBER):
        return [NUMBER]

    p_error = t_error

    @classmethod
    def generate(cls, raw, *parse_args, **parse_kw):
        result = cls.parse(raw, *parse_args, **parse_kw)
        return cid(*map("".join, zip(*result)))
