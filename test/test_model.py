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
    Structure,
    Macro,
    Initializer,
    OpDeclareAssign,
    BranchSwitch,
    SwitchCase,
    Call,
    Enumeration,
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
            sf = file.generate(
                inherit_global_headers = isinstance(file, Header)
            )

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
            is_header = isinstance(file, Header)
            sf_first = file.generate(inherit_global_headers = is_header)
            sf_second = file.generate(inherit_global_headers = is_header)

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


class TestForwardDeclaration(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestForwardDeclaration, self).setUp()
        name = type(self).__name__

        src = Source(name.lower() + ".c")

        a = Structure("A")
        a.append_field(a.gen_var("next", pointer = True))

        b = Structure("B")
        b.append_field(a.gen_var("next", pointer = True))

        src.add_types([a, b])

        src_content = """\
/* {} */
typedef struct A A;

struct A {{
    A *next;
}};

typedef struct B {{
    A *next;
}} B;

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


class TestCrossDeclaration(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestCrossDeclaration, self).setUp()

        src = Source(type(self).__name__.lower() + ".c")

        a = Structure("A")
        b = Structure("B")

        b.append_field(a.gen_var("ref", pointer = True))
        a.append_field(b.gen_var("ref", pointer = True))

        src.add_types([a, b])

        src_content = """\
/* {} */
typedef struct B B;

typedef struct A {{
    B *ref;
}} A;

struct B {{
    A *ref;
}};

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


class TestForwardDeclarationHeader(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestForwardDeclarationHeader, self).setUp()
        name = type(self).__name__

        hdr = Header(name.lower() + ".h")
        src = Source(name.lower() + ".c")

        a = Structure("A")
        a.append_field(a.gen_var("next", pointer = True))

        b = Structure("B")
        b.append_field(a.gen_var("next", pointer = True))

        hdr.add_type(a)
        hdr_content = """\
/* {path} */
#ifndef INCLUDE_{fname_upper}_H
#define INCLUDE_{fname_upper}_H
typedef struct A A;

struct A {{
    A *next;
}};

#endif /* INCLUDE_{fname_upper}_H */
""".format(path = hdr.path, fname_upper = name.upper())

        src.add_type(b)
        src_content = """\
/* {} */
#include "{}"

typedef struct B {{
    A *next;
}} B;

""".format(src.path, hdr.path)

        self.files = [
            (hdr, hdr_content),
            (src, src_content)
        ]


class TestMacroType(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestMacroType, self).setUp()
        name = type(self).__name__

        hdr = Header(name.lower() + ".h")
        hdr.add_type(Macro("QTAIL_ENTRY", args = ["type"]))

        struct = Structure("StructA")
        struct.append_field(
            Type["QTAIL_ENTRY"].gen_var("entry",
                macro_initializer = Initializer({ "type":  struct })
            )
        )
        struct.append_field(
            struct.gen_var("next", pointer = True)
        )
        hdr.add_type(struct)

        hdr_content = """\
/* {path} */
#ifndef INCLUDE_{fname_upper}_H
#define INCLUDE_{fname_upper}_H
#define QTAIL_ENTRY(type)
typedef struct StructA StructA;

struct StructA {{
    QTAIL_ENTRY(StructA) entry;
    StructA *next;
}};

#endif /* INCLUDE_{fname_upper}_H */
""".format(path = hdr.path, fname_upper = name.upper())

        self.files = [
            (hdr, hdr_content)
        ]


class TestSeparateCases(FunctionTreeTestDoubleGenerationHelper, TestCase):

    def setUp(self):
        super(TestSeparateCases, self).setUp()

        src = Source(type(self).__name__.lower() + ".c")

        i = Type["int"].gen_var("i")
        src.add_type(
            Function(
                name = "func_a",
                body = BodyTree()(
                    Declare(OpDeclareAssign(i, 0)),
                    BranchSwitch(i, separate_cases = True)(
                        SwitchCase(1),
                        SwitchCase(2)
                    )
                )
            )
        )

        src_content = """\
/* {} */
void func_a(void)
{{
    int i = 0;
    switch (i) {{
    case 1:
        break;

    case 2:
        break;

    default:
        break;
    }}
}}

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


class TestHeaderInclusion(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestHeaderInclusion, self).setUp()
        name = type(self).__name__

        f = Function(name = "test_f")
        f_def = f.gen_definition()

        hdr = Header(name.lower() + ".h").add_type(f)
        hdr_content = """\
/* {path} */
#ifndef INCLUDE_{fname_upper}_H
#define INCLUDE_{fname_upper}_H
void test_f(void);
#endif /* INCLUDE_{fname_upper}_H */
""".format(path = hdr.path, fname_upper = name.upper())

        src1 = Source(name.lower() + ".c").add_type(f_def)
        src1_content = """\
/* {} */
void test_f(void) {{}}

""".format(src1.path)

        src2 = Source(name.lower() + "2.c").add_type(
            Function(
                name = "func_a",
                body = BodyTree()(
                    Call(f_def) # use function definition to Call
                )
            )
        )
        src2_content = """\
/* {} */
#include "{}"

void func_a(void)
{{
    test_f();
}}

""".format(src2.path, hdr.path)

        self.files = [
            (hdr, hdr_content),
            (src1, src1_content),
            (src2, src2_content)
        ]


class TestPointerReferences(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestPointerReferences, self).setUp()
        name = type(self).__name__

        try:
            h = Header["type_a.h"]
        except:
            h = Header("type_a.h")
        h.add_type(Type("a", incomplete = False, base = False))

        src = Source(name.lower() + ".c").add_type(
            Structure("s", Type["a"].gen_var("next", pointer = True))
        )

        src_content = """\
/* {} */
#include "type_a.h"

typedef struct s {{
    a *next;
}} s;

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


class TestEnumerations(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestEnumerations, self).setUp()
        name = type(self).__name__

        try:
            h = Header["enums.h"]
        except:
            h = Header("enums.h")
        h.add_type(Enumeration("A", {"one": 1, "two": 2}))

        a = Type["int"].gen_var("a")
        b = Type["int"].gen_var("b")
        c = Type["int"].gen_var("c")

        src = Source(name.lower() + ".c").add_types([
            Enumeration("B", {"three": 3, "four": 4}, "B"),
            Function(name = "main", body = BodyTree()(
                Declare(a, b, c),
                OpAssign(a, Type["A"].get_field("one")),
                OpAssign(b, Type["B"].get_field("three")),
                OpAssign(c, Type["four"])
            ))
        ])

        src_content = """\
/* {} */
#include "enums.h"

enum B {{
    three = 3,
    four = 4
}};

void main(void)
{{
    int a, b, c;
    a = one;
    b = three;
    c = four;
}}

""".format(src.path)

        self.files = [
            (src, src_content)
        ]

if __name__ == "__main__":
    main()
