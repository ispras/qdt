from os.path import (
    dirname,
    join
)
from os import (
    popen
)
from unittest import (
    TestCase,
    main
)
from common import (
    git_diff2delta_intervals
)
from common import (
    same
)


class LineAdaptationTestHelper(object):

    def test(self):
        tests_dir = join(dirname(__file__), "line_adaptation_tests")
        diff = popen("git diff -U0 %s %s" % (
            join(tests_dir, self._old), join(tests_dir, self._new)
        )).read()
        intrvls = git_diff2delta_intervals(diff)
        lines_map = {}

        for line in self._lines_map:
            if intrvls[line] is not None:
                lines_map[line] = line + intrvls[line]
            else:
                lines_map[line] = None

        try:
            eq = same(lines_map, self._lines_map)
        except:
            print("\nIntervals are different")
            eq = False

        self.assertTrue(eq, "Intervals differ.")


class TestLineAdaptation1(TestCase, LineAdaptationTestHelper):

    def setUp(self):
        self._old = "1/curr"
        self._new = "1/base"
        # 'base' to 'curr' lines mapping
        self._lines_map = {1: 1, 2: 3, 3: 4}


class TestLineAdaptation2(TestCase, LineAdaptationTestHelper):

    def setUp(self):
        self._old = "2/curr"
        self._new = "2/base"
        # 'base' to 'curr' lines mapping
        self._lines_map = {1: 1, 2: 2, 3: None, 4: 3}


if __name__ == "__main__":
    main()
