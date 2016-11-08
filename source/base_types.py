from source.model import Type, Header, Function

def add_base_types():
    Type(name = "void", incomplete = True, base = True)
    Type(name = "int", incomplete = False, base = True)
    Type(name = "unsigned", incomplete = False, base = True)
    Type(name = "unsigned int", incomplete = False, base = True)
    Type(name = "const char", incomplete = False, base = True)

    Header("stdint.h", is_global=True).add_types([
        Type(name = "uint64_t", incomplete = False, base = False)
        , Type(name = "uint32_t", incomplete = False, base = False)
        , Type(name = "uint16_t", incomplete = False, base = False)
        , Type(name = "uint8_t", incomplete = False, base = False)
        , Type(name = "uintptr_t", incomplete = False, base = False)
        ])

    Header("stdbool.h", is_global=True).add_types([
        Type(name = "bool", incomplete = False, base = False)
        ])

    Header("stdio.h", is_global=True).add_types([
        Function("printf")
        ])
