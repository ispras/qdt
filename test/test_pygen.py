from unittest import (
    TestCase,
    main
)
from examples import (
    Q35Project_2_6_0
)
from common import (
    ObjectVisitor,
    BreakVisiting,
    PyGenerator
)
from common.pygen import ( # private variable
    const_types
)
from six import (
    StringIO
)
from six.moves import (
    zip_longest
)
from collections import (
    Counter,
    defaultdict
)
from pprint import (
    pprint
)
import qdt


class DictVisitor(ObjectVisitor):

    def __init__(self, root):
        super(DictVisitor, self).__init__(root, field_name = "__dict__")
        self.seq = []
        self.visited = set()

    def on_visit(self):
        cur, visited = self.cur, self.visited
        cid = id(cur)
        if cid in visited:
            raise BreakVisiting()
        visited.add(cid)

        path = self.path
        if path[-1][1] == "id2node":
            raise BreakVisiting()
        path_names = tuple(n[1] for n in path[1:])
        path_refs = tuple(n[0] for n in path[1:])
        self.seq.append((path_names, cur, path_refs))


class Undefined(object):

    def __repr__(self):
        return "undef"


undef = Undefined()


def cmp_verbose(obj1, obj2):
    sides = defaultdict(lambda : [(undef, undef), (undef, undef)])
    for s1, s2 in zip_longest(
        DictVisitor(obj1).visit().seq, DictVisitor(obj2).visit().seq
    ):
        if s1 is not None:
            p1, o1, r1 = s1
            sides[p1][0] = o1, r1
        if s2 is not None:
            p2, o2, r2 = s2
            sides[p2][1] = o2, r2

    diff = {}

    for path, ((o1, r1), (o2, r2)) in sides.items():
        if type(o1) is not type(o2):
            eq = False
        elif o1 is None:
            eq = True
        elif type(o1) in (list, tuple, set):
            eq = len(o1) == len(o2)
        elif type(o1) is dict:
            eq = Counter(o1.keys()) == Counter(o2.keys())
        elif isinstance(o1, const_types):
            eq = o1 == o2
        else:
            try:
                d1, d2 = o1.__dict__, o2.__dict__
            except:
                eq = False
            else:
                eq = Counter(d1.keys()) == Counter(d2.keys())
        if not eq:
            diff[path] = (o1, o2)

    for path in diff:
        ppath = path
        while ppath:
            ppath = ppath[:-1]
            s1, s2 = sides[ppath]
            if s1[0] is not undef and s2[0] is not undef:
                break
#
#         for p, o1, o2 in zip_longest(ppath, s1[1], s2[1]):
#             print("\n\n%s\n    %s\n-\n    %s" % (p, o1, o2))\

        print("\n")
        pprint(ppath)
        pprint(s1[1][-1])
        pprint(s2[1][-1])

    # pprint(diff)


class TestPyGenerator(TestCase):

    def setUp(self):
        self._original = Q35Project_2_6_0()

    def test(self):
        buf = StringIO()
        self._generator = g = PyGenerator(backend = buf)
        g.serialize(self._original)
        code = buf.getvalue()
        with open("_code.py", "w") as f:
            f.write(code)
        res = {}
        exec(code, dict(qdt.__dict__), res)
        loaded = res[self._generator.nameof(self._original)]
        eq = loaded == self._original
        # cmp_verbose(self._original, loaded)
        self.assertEqual(loaded, self._original, "Loaded object differs.")


if __name__ == "__main__":
    main()
