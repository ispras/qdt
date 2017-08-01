from .model import \
    Type, \
    Header, \
    Function, \
    Macro

def add_base_types():
    Type(name = "void", incomplete = True, base = True)
    Type(name = "int", incomplete = False, base = True)
    Type(name = "unsigned", incomplete = False, base = True)
    Type(name = "unsigned int", incomplete = False, base = True)
    Type(name = "const char", incomplete = False, base = True)

    try:
        h = Header.lookup("stdint.h")
    except:
        h = Header("stdint.h", is_global=True)

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
        h = Header("stddef.h", is_global=True)

    h.add_types([
        Type(name = "size_t", incomplete = False, base = False),
        Macro("offsetof")
    ])

    try:
        h = Header.lookup("stdbool.h")
    except:
        h = Header("stdbool.h", is_global=True)

    h.add_types([
        Type(name = "true", incomplete = False, base = False),
        Type(name = "false", incomplete = False, base = False),
        Type(name = "bool", incomplete = False, base = False)
        ])

    try:
        h = Header.lookup("stdio.h")
    except:
        h = Header("stdio.h", is_global=True)

    h.add_types([
        Type("ssize_t", incomplete = False, base = False),
        Function("printf"),
        Function("fprintf"),
        Type("FILE")
        ])

    try:
        h = Header.lookup("string.h")
    except:
        h = Header("string.h", is_global=True)

    h.add_types([
        Function("memcpy")
        ])
