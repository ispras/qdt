from common import (
    ee
)
from qemu import (
    QemuTypeName
)
from random import (
    randrange
)


QTN_AUTO_SEARCH = ee("QTN_AUTO_SEARCH")


def names(qtn):
    return (
        qtn.for_id_name,
        qtn.for_header_name,
        qtn.for_struct_name,
        qtn.type_macro
    )


def qtn_char(c):
    # low ["0"; "9"] middle0 ["A", "Z"] middle1 ["a"; "z"] high
    if c < "0":
        # low
        return False
    # ["0"; "9"] middle0 ["A", "Z"] middle1 ["a"; "z"] high
    if "z" < c:
        # high
        return False
    # ["0"; "9"] middle0 ["A", "Z"] middle1 ["a"; "z"]
    if c < "A":
        # ["0"; "9"] middle0
        return c <= "9"
    # ["A", "Z"] middle1 ["a"; "z"]
    if "Z" < c:
        # middle1 ["a"; "z"]
        return "a" <= c
    # ["A", "Z"]
    return True

# Replacements for characters
qtn_id_char_map = {
    "/" : ""
    # default : c if qtn_char(c) else "_"
}

qtn_struct_char_map = {
    # default : c if qtn_char(c) else ""
}

qtn_macro_char_map = qtn_id_char_map
# same default


class QemuTypeNameOld(object):

    def __init__(self, name):
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value.strip()

        tmp = ""
        for c in self._name.lower():
            if c in qtn_id_char_map:
                tmp += qtn_id_char_map[c]
            else:
                tmp += c if qtn_char(c) else "_"

        self.for_id_name = tmp
        self.for_header_name = tmp

        tmp = ""
        for c in self._name:
            if c in qtn_struct_char_map:
                tmp += qtn_struct_char_map[c]
            else:
                tmp += c if qtn_char(c) else ""

        self.for_struct_name = tmp

        tmp = ""
        for c in self._name.upper():
            if c in qtn_macro_char_map:
                tmp += qtn_macro_char_map[c]
            else:
                tmp += c if qtn_char(c) else "_"

        self.for_macros = tmp
        self.type_macro = "TYPE_%s" % tmp


def main():
    # automatic search
    while QTN_AUTO_SEARCH:
        test_len = randrange(3, 10)
        test = "".join(chr(randrange(32, 126)) for _ in range(test_len))

        # print the test to prevent loss when crashing
        print("Current test: %s" % test)

        qtn_new = names(QemuTypeName(test))
        qtn_old = names(QemuTypeNameOld(test))
        if qtn_new != qtn_old:
            print("DIFFER: ", qtn_new, qtn_old)

    # manual debug
    test = "a_2/2"
    print(names(QemuTypeName(test)))


if __name__ == "__main__":
    main()
