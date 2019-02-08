from os.path import (
    split,
    dirname,
    join
)
from os import (
    environ
)
from unittest import (
    TestCase,
    main
)
from common import (
    git_diff2delta_intervals,
    same
)
from git import (
    Repo
)
from subprocess import (
    PIPE,
    Popen
)


test_dir = dirname(__file__)

class LineAdaptationTestHelper(object):

    def _check(self, diff):
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

    def test(self):
        tests_dir = join(test_dir, "line_adaptation_tests")
        diff, _ = Popen(["git", "diff", "--no-index", "-U0",
                join(tests_dir, self._old), join(tests_dir, self._new)
            ],
            stdout = PIPE
        ).communicate()

        self._check(diff)

    def test_gitpython(self):
        repo_dir = join(test_dir, "line_adaptation_tests", "gitrepo", "_git")

        # gitpython launches git during diff obtaining
        environ["GIT_DIR"] = repo_dir
        repo = Repo(repo_dir)
        diff = repo.commit("curr").diff("base",
            create_patch = True,
            unified = 0
        )
        file_name = split(self._new)[0]
        for change in diff:
            if change.b_rawpath == file_name:
                self._check(change.diff)
                break
        else:
            self.fail("No diff for file " + file_name)


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
