__all__ = [
    "gen_printf_format"
]

from .function.tree import (
    StrConcat,
)
from .model import (
    Type,
)

from math import (
    ceil,
    log,
)
from re import (
    compile,
)

re_std_int = compile(r"(?P<unsigned>u?)int(?P<bits>\d+)_t")


def gen_printf_format(type_,
    base = 10,
    width = None,
    leading = "",
):
    """
@param width
    True: automatic
    [number]: exact
@param leading
    printf "understands" space (" ") and zero ("0")
    """
    if base == 8:
        base_prefix = "0o"
        specifier = "o"
    elif base == 10:
        base_prefix = ""
        specifier = "d"
    elif base == 16:
        base_prefix = "0x"
        specifier = "x"
    else:
        raise NotImplementedError("base %s is not implemented" % base)

    name = type_.name

    mi = re_std_int.match(name)

    if mi:
        unsigned = bool(mi["unsigned"])
        if specifier == "d" and unsigned:
            specifier = "u"
        bits = mi["bits"]

        if width is True:
            width = ceil(int(bits) * log(2) / log(base))

        if width:
            width = str(width)
        else:
            width = ""

        macro = Type["PRI" + specifier + bits]
        return StrConcat(
            base_prefix
                + "%"
                + (leading if (width and leading) else "")
                + width,
            macro,
        )
    else:
        raise NotImplementedError("type name '%s' is not implemented" % name)
