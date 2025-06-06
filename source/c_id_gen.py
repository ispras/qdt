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
# There is a safe form of character, which is as close to the original
# as possible.
cidchar = nt("cidchar", "instance struct macro safe")
cid = nt("cid", "instance struct macro safe")

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
        t.value = cidchar(c, c, c.upper(), c)
        return t

    def t_UPPER(t):
        r"[A-Z]"
        c = t.value
        t.value = cidchar(c.lower(), c, c, c)
        return t

    # Special replacements for forbidden characters.

    # Slash is just discarded.
    # Ex.: "I/O" ("Input/Output") should be handled as IO, etc.
    def t_SLASH(t):
        r"[/\\]"
        t.value = cidchar('', '', '', '_')
        return t

    # Replace forbidden characters with '_'.
    # But `struct` name must not have `_`.
    def t_FORBIDDEN(t):
        r"."
        t.value = cidchar('_', '', '_', '_')
        return t

    def t_error(t):
        raise NotImplementedError(
            "You just found a bug in C Id generator!"
        )

    # Parser produces list of `cidchar`s those will be used for thing
    # construction.

    def s_result(base):
        return base

    def s_result__empty():
        return [cidchar('', '', '', '_')]

    def s_result__discard_leading_digits(digits, base):
        return base

    def s_result__discard_leading_separators(separators, base):
        return base

    def s_base__0(capitalized):
        return capitalized

    def s_base__1(word):
        return word

    def s_base__2(separated):
        # Strip separator to the right.
        return separated[:-1]

    def s_base__3(enumerated):
        return enumerated

    def s_capitalized(capitalizer, word):
        # Capitalize structure name.
        return capitalizer + [
            word[0]._replace(struct = word[0].struct.capitalize())
        ] + word[1:]

    def s_separated(separatible, separators):
        # Take only first separator, discard rest.
        return separatible + separators[:1]

    def s_enumerated(enumeratible, digits):
        return enumeratible + digits

    def s_capitalizer__0(separated):
        return separated

    def s_capitalizer__1(enumerated):
        return enumerated

    def s_separatible__0(capitalized):
        return capitalized

    def s_separatible__1(word):
        return word

    def s_separatible__2(enumerated):
        return enumerated

    def s_enumeratible__0(capitalized):
        return capitalized

    def s_enumeratible__1(word):
        return word

    def s_enumeratible__2(separated):
        return separated

    def s_word(word__0, word__1):
        return word__0 + word__1

    def s_word__LOWER(LOWER):
        return [LOWER]

    def s_word__UPPER(UPPER):
        return [UPPER]

    def s_separators(separators__0, separators__1):
        return separators__0 + separators__1

    def s_separators__SLASH(SLASH):
        return [SLASH]

    def s_separators__FORBIDDEN(FORBIDDEN):
        return [FORBIDDEN]

    def s_digits(digits__0, digits__1):
        return digits__0 + digits__1

    def s_digits__NUMBER(NUMBER):
        return [NUMBER]

    p_error = t_error

    @classmethod
    def generate(cls, raw, *parse_args, **parse_kw):
        try:
            result = cls.parse(raw, *parse_args, **parse_kw)
        except:
            pass
        else:
            return cid(*map("".join, zip(*result)))

        print("%s: failed to parse %r" % (cls, raw))
        parse_kw["debug"] = True
        cls.parse(raw, *parse_args, **parse_kw)
