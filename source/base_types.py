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
    Type(name = "const char", incomplete = False, base = True)
    Type(name = "char", incomplete = False, base = True)

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
        Function("printf"),
        Function("fprintf"),
        Type("FILE")
    ])

    try:
        h = Header.lookup("string.h")
    except:
        h = Header("string.h", is_global = True)

    h.add_types([
        Function("memcpy")
    ])

    try:
        h = Header.lookup("byteswap.h")
    except:
        h = Header("byteswap.h", is_global = True)

    # If "bswap_64", "bswap_32" and "bswap_16" are not macros or do not exists
    # then they must be added explicitly.
    if not Type.exists("bswap_64"):
        h.add_types([
            Function("bswap_64"),
            Function("bswap_32"),
            Function("bswap_16")
        ])

    try:
        h = Header.lookup("stdlib.h")
    except:
        h = Header("stdlib.h", is_global = True)

    h.add_types([
        Function("abort")
    ])
