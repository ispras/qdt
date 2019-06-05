from unittest import (
    TestCase, # XXX: is not used yet
    main
)
from six import (
    StringIO
)
from source import (
    Type,
    Header,
    Source,
    Function,
    BodyTree,
    Declare,
    OpAssign,
    OpAdd,
    Label,
    Goto,
    add_base_types
)
from common import (
    ee
)
from os.path import (
    join,
    dirname
)
from difflib import (
    unified_diff
)


MODEL_VERBOSE = ee("MODEL_VERBOSE")
SAVE_CHUNK_GRAPH = ee("SAVE_CHUNK_GRAPH")


verbose_dir = join(dirname(__file__), "model_code")


class SourceModelTestHelper(object):

    def setUp(self):
        Type.reg = {}
        Header.reg = {}
        add_base_types()

    def test(self):
        for file, content in self.files:
            # XXX: file is reserved
            sf = file.generate()

            if SAVE_CHUNK_GRAPH:
                sf.gen_chunks_gv_file(
                    join(verbose_dir, file.path + ".chunks.gv")
                )

            sio = StringIO()
            sf.generate(sio)
            gen_content = sio.getvalue()

            if MODEL_VERBOSE:
                with open(join(verbose_dir, file.path), "w") as f:
                    f.write(gen_content)

            self._compate_content(content, gen_content)

    def _compate_content(self, expected, generated):
        if expected == generated:
            return

        print("\n".join(unified_diff(
            expected.split('\n'),
            generated.split('\n')
        )))

        self.fail("Generated code differs from expected value")


class FunctionTreeTestDoubleGenerationHelper(object):

    def setUp(self):
        Type.reg = {}
        Header.reg = {}
        add_base_types()

    def test(self):
        for file, content in self.files:
            # XXX: file is reserved
            sf_first = file.generate()
            sf_second = file.generate()

            sio_first = StringIO()
            sio_second = StringIO()

            sf_first.generate(sio_first)
            sf_second.generate(sio_second)

            first_gen_content = sio_first.getvalue()
            second_gen_content = sio_second.getvalue()

            if MODEL_VERBOSE:
                with open(join(verbose_dir, "gen1" + file.path), "w") as f:
                    f.write(first_gen_content)
                with open(join(verbose_dir, "gen2" + file.path), "w") as f:
                    f.write(second_gen_content)

            self.assertEqual(first_gen_content, content)
            self.assertEqual(second_gen_content, first_gen_content)


class TestLabelAndGotoGeneration(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestLabelAndGotoGeneration, self).setUp()
        name = type(self).__name__

        src = Source(name.lower() + ".c")

        lbl = Label("begin")
        i = Type["int"].gen_var("i")

        src.add_type(Function(
            name = "main",
            body = BodyTree()(
                Declare(i),
                lbl,
                OpAssign(i, OpAdd(i, 1)),
                Goto(lbl)
            )
        ))

        src_content = """\
/* {} */
void main(void)
{{
    int i;
begin:
    i = i + 1;
    goto begin;
}}

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


if __name__ == "__main__":
    main()
