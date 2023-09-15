__all__ = [
    "iter_tokens",
]

from libe.common.pypath import (
    pypath,
)
with pypath("...ply"):
    from ply.lex import (
        LexToken,
    )
    from ply.yacc import (
        YaccSymbol,
    )


def iter_tokens(root):
    "Iterates over tokens in parse tree."

    if isinstance(root, LexToken):
        yield root
    else:
        if isinstance(root, YaccSymbol):
            children = root.value
        else: # root is a container
            children = root

        for child in children:
            for tok in iter_tokens(child):
                yield tok
