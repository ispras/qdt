__all__ = [
    "one_of"
  , "word"
  , "CWords"
]


one_of = lambda words : "((" + ")|(".join(words) + "))(?=[ \t]|$)"

def word(*words):
    def decorate(func):
        func.__doc__ = one_of(words)
        return func
    return decorate


class CWords:
    # priority over t_IDENTIFIER
    @staticmethod
    @word(
        "_Alignas",
    )
    def t_ALIGN_AS(t):
        return t

    @staticmethod
    @word(
        "_Atomic",
    )
    def t_ATOMIC(t):
        return t

    @staticmethod
    @word(
        "enum",
    )
    def t_ENUM(t):
        return t

    @staticmethod
    @word(
        "struct",
    )
    def t_STRUCT(t):
        return t

    @staticmethod
    @word(
        "union",
    )
    def t_UNION(t):
        return t

    @staticmethod
    @word(
        "sizeof",
    )
    def t_SIZEOF(t):
        return t

    @staticmethod
    @word(
        "if",
    )
    def t_IF(t):
        return t

    @staticmethod
    @word(
        "else",
    )
    def t_ELSE(t):
        return t

    @staticmethod
    @word(
        "while",
    )
    def t_WHILE(t):
        return t

    @staticmethod
    @word(
        "do",
    )
    def t_DO(t):
        return t

    @staticmethod
    @word(
        "for",
    )
    def t_FOR(t):
        return t

    @staticmethod
    @word(
        "switch",
    )
    def t_SWITCH(t):
        return t

    @staticmethod
    @word(
        "case",
    )
    def t_CESE(t):
        return t

    @staticmethod
    @word(
        "default",
    )
    def t_DEFAULT(t):
        return t

    @staticmethod
    @word(
        "break",
    )
    def t_BREAK(t):
        return t

    @staticmethod
    @word(
        "continue",
    )
    def t_CONTINUE(t):
        return t

    @staticmethod
    @word(
        "inline",
        "_Noreturn",
    )
    def t_FUNCTION_SPECIFIER(t):
        return t

    @staticmethod
    @word(
        "void",
        "char",
        "short",
        "int",
        "long",
        "float",
        "double",
        "signed",
        "unsigned",
        "_Bool",
        "_Complex",
    )
    def t_BASE_TYPE_SPECIFIER(t):
        return t

    @staticmethod
    @word(
        "typedef",
        "extern",
        "static",
        "_Thread_local",
        "auto",
        "register",
    )
    def t_STORAGE_CLASS_SPECIFIER(t):
        return t

    @staticmethod
    @word(
        "const",
        "restrict",
        "volatile",
        # "_Atomic",
    )
    def t_TYPE_QUALIFIER(t):
        return t

    @staticmethod
    @word(
        "return",
    )
    def t_RETURN(t):
        return t

    @staticmethod
    def t_IDENTIFIER(t):
        "[_a-zA-Z][_a-zA-Z0-9]*"
        return t
