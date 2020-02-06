__all__ = [
    "CachedDIE"
]


class CachedDIE(object):
    "Common class for things defined by a debugging information entry."
    # TODO: inherit all such things from that class.

    def __init__(self, dic, die):
        self.dic = dic
        self.die = die

        # This list is lazily filled.
        # See `find_DIE_attr`.
        self._die_specs = [die]

    def find_DIE_attr(self, name):
        # The `die` may complete another DIE referenced
        # by `DW_AT_specification` attribute.
        # See: 2.13.2 Declarations Completing Non-Defining Declarations
        # of DWARF v5
        for die in self._die_specs:
            try:
                return die.attributes[name]
            except KeyError:
                continue

        DIE_by_attr = self.dic.get_DIE_by_attr
        specs = self._die_specs

        while True:
            try:
                spec = die.attributes["DW_AT_specification"]
            except KeyError:
                break
            die = DIE_by_attr(spec, die.cu)
            specs.append(die)
            try:
                return die.attributes[name]
            except KeyError:
                continue

        raise KeyError(name)

    def __getitem__(self, name):
        return self.find_DIE_attr(name)
