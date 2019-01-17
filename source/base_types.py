__all__ = [
    "add_base_types"
]

from .model import (
    Type,
    Header,
    Function,
    Macro
)

def add_base_types():
    Type(name = "void", incomplete = True, base = True)
    Type(name = "int", incomplete = False, base = True)
    Type(name = "unsigned", incomplete = False, base = True)
    Type(name = "unsigned int", incomplete = False, base = True)
    Type(name = "short int", incomplete = False, base = True)
    Type(name = "unsigned short int", incomplete = False, base = True)
    Type(name = "long int", incomplete = False, base = True)
    Type(name = "unsigned long", incomplete = False, base = True)
    Type(name = "unsigned long int", incomplete = False, base = True)
    Type(name = "long long int", incomplete = False, base = True)
    Type(name = "unsigned long long int", incomplete = False, base = True)
    Type(name = "const char", incomplete = False, base = True)
    Type(name = "char", incomplete = False, base = True)
    Type(name = "signed char", incomplete = False, base = True)
    Type(name = "unsigned char", incomplete = False, base = True)
    Type(name = "double", incomplete = False, base = True)
    Type(name = "long double", incomplete = False, base = True)

    try:
        h = Header.lookup("stdint.h")
    except:
        h = Header("stdint.h", is_global = True)

    h.add_types([
        Type(name = "uint64_t", incomplete = False, base = False)
        , Type(name = "uint32_t", incomplete = False, base = False)
        , Type(name = "uint16_t", incomplete = False, base = False)
        , Type(name = "uint8_t", incomplete = False, base = False)
        , Type(name = "const uint8_t", incomplete = False, base = False)
        , Type(name = "uintptr_t", incomplete = False, base = False)
        , Type(name = "int64_t", incomplete = False, base = False)
        , Type(name = "int32_t", incomplete = False, base = False)
        , Type(name = "int16_t", incomplete = False, base = False)
        , Type(name = "int8_t", incomplete = False, base = False)
        , Type(name = "intmax_t", incomplete = False, base = False)
        , Type(name = "uintmax_t", incomplete = False, base = False)
    ])

    try:
        h = Header.lookup("stddef.h")
    except:
        h = Header("stddef.h", is_global = True)
        h.add_types([
            Macro("offsetof")
        ])

    h.add_types([
        Type(name = "size_t", incomplete = False, base = False),
        Type(name = "ptrdiff_t", incomplete = False, base = False)
    ])

    try:
        h = Header.lookup("stdbool.h")
    except:
        h = Header("stdbool.h", is_global = True)

    # If "true", "false" and "bool" are not macros or do not exists then they
    # must be added explicitly.
    if not Type.exists("true"):
        h.add_types([
            Type(name = "true", incomplete = False, base = False),
            Type(name = "false", incomplete = False, base = False),
            Type(name = "bool", incomplete = False, base = False)
        ])

    try:
        h = Header.lookup("stdio.h")
    except:
        h = Header("stdio.h", is_global = True)

    h.add_types([
        Type("ssize_t", incomplete = False, base = False),
        Function(name = "printf"),
        Function(name = "fprintf"),
        Type("FILE")
    ])

    try:
        h = Header.lookup("string.h")
    except:
        h = Header("string.h", is_global = True)

    h.add_types([
        Function(name = "memcpy")
    ])

    # If "bswap_64", "bswap_32" and "bswap_16" are not macros or do not exists
    # then they must be added explicitly.
    if not Type.exists("bswap_64"):
        try:
            h = Header["byteswap.h"]
        except:
            h = Header("byteswap.h", is_global = True)

        h.add_types([
            Function(name = "bswap_64"),
            Function(name = "bswap_32"),
            Function(name = "bswap_16")
        ])

    try:
        h = Header.lookup("stdlib.h")
    except:
        h = Header("stdlib.h", is_global = True)

    h.add_types([
        Function(name = "abort")
    ])

    try:
        h = Header.lookup("wchar.h")
    except:
        h = Header("wchar.h", is_global = True)

    h.add_types([
        Type(name = "wint_t", incomplete = False, base = False),
        Type(name = "wchar_t", incomplete = False, base = False)
    ])