from unittest import (
    main
)
from common import (
    ee,
    pypath
)
from os.path import (
    dirname,
    join
)
from debug import (
    git_repo_by_dwarf,
    GitLineVersionAdapter,
    Watcher,
    InMemoryELFFile,
    DWARFInfoCache,
    Runtime
)
with pypath("..pyrsp.test"):
    from tests import (
        TestUser
    )


test_dir = join(dirname(__file__), "debug_tests")
verb = ee("TEST_WATCHER_VERBOSE", "False")


def get_glv_adapter(di):
    return GitLineVersionAdapter(git_repo_by_dwarf(di))


class BitFieldsWatcher(Watcher):

    def __init__(self, test, *a, **kw):
        super(BitFieldsWatcher, self).__init__(*a, **kw)
        self._test = test

    def on_main(self):
        "main.c:16 bccaa903d7e8ccd4fa9faa4df004948a3e8dd912"
        # Note, this SHA1 is of one of previous commits in QDT history:
        # "test: add C program for testing of bit fields support ..."
        rt = self.rt

        s = rt["s"]

        values = tuple(map(
            lambda v: v.fetch(),
            (s[f] for f in ("j", "k", "m", "n"))
        ))

        if self.verbose:
            print(values)

        self._test.assertEqual(values, (1, 2, 3, 4))

        s2 = rt["s2"]

        values = tuple(map(
            lambda v: v.fetch(),
            (s2[f] for f in ("a", "b", "c"))
        ))

        if self.verbose:
            print(values)

        self._test.assertEqual(values, (5, 6, 7))

class TestBitFields(TestUser):
    SRC = join(test_dir, "bitfields", "main.c")
    EXE = SRC[:-1] + "exe"

    def setUp(self):
        super(TestBitFields, self).setUp()

        self._elf = InMemoryELFFile(self.EXE)
        self._dic = DWARFInfoCache(self._elf.get_dwarf_info(),
            symtab = self._elf.get_section_by_name(".symtab")
        )
        self._rt = Runtime(self._target, self._dic)
        glva = get_glv_adapter(self._dic.di)

        w = BitFieldsWatcher(self, self._dic,
            line_adapter = glva,
            verbose = verb
        )
        w.init_runtime(self._rt)

    def test_bitfields(self):
        self._target.run(setpc = False)

if __name__ == "__main__":
    main()
