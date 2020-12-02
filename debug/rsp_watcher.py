__all__ = [
    "re_symbol"
  , "iter_br_cbs"
  , "RSPWatcher"
]

from inspect import (
    getmembers,
    isroutine,
)
from re import (
    compile,
)
from .symtab import (
    SymTab,
)

re_symbol = compile(u"(\\w|_)(\\w|\\d|_)*")


def iter_br_cbs(obj):
    for name, cb in getmembers(obj, predicate = isroutine):
        if not name.startswith("on_"):
            continue
        doc = cb.__doc__
        if not doc:
            continue
        for l in doc.splitlines():
            sym = l.strip()
            if re_symbol.match(sym):
                yield cb, sym


class RSPWatcher(object):
    """ A breakpoint setting helper based on .symtab (symbol table) only.

A method with such a signature is treated as a breakpoint callback:

    def on_some_symbol(self):
        "some_symbol"
        # Write breakpoint script here.
        # You can use `self.rsp` and `self.symtab`.

First line in `method.__doc__` string that matches `re_symbol` is used as
name of symbol. The breakpoint is set on address of the symbol according to
.symtab section.

    """

    def __init__(self, rsp, elf_file_name):
        self.rsp = rsp
        self.symtab = symtab = SymTab(elf_file_name)
        address_map = symtab.address_map

        for cb, sym in iter_br_cbs(self):
            addr_str = b"%x" % address_map[sym]
            rsp.set_br_a(addr_str, cb)
