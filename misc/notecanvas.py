from os.path import (
    join,
    expanduser
)
from common import (
    Persistent
)


class compat(object):

    def __init__(self, **forward):
        self.__forward = forward

    __pygen_deps__ = ("_compat__forward",)

    def __gen_code__(self, g):
        g.reset_gen(self)
        g.gen_args(self, pa_names = True)
        for arg, v in self._compat__forward.items():
            g.gen_field(arg + " = ")
            g.pprint(v)
        g.gen_end()


class Note(compat):

    def __init__(self, x, y, text = None, **kw):
        super(Note, self).__init__(**kw)

        self.x = x
        self.y = y
        self.text = text

    def __var_base__(self):
        return "n"


def main():
    with Persistent(expanduser(join("~", ".notecanvas.py")),
        glob = globals(),
        notes = []
    ) as p:
        if not p.notes:
            p.notes.append(Note(0xdead, 0xbeef))
        else:
            print(p.notes[0].text)
        p.notes[0].text = "foo"

"""
class Note(compat):

    def __init__(self, x, y, **kw):
        super(Note, self).__init__(**kw)

        self.x = x
        self.y = y


def main():
    with Persistent(expanduser(join("~", ".notecanvas.py")),
        glob = globals(),
        notes = []
    ) as p:
        if not p.notes:
            p.notes.append(Note(0xdead, 0xbeef))
"""

if __name__ == "__main__":
    exit(main())
