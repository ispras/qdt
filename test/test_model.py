from unittest import (
    TestCase,
    main
)
from six import (
    StringIO
)
from source import (
    OpaqueCode,
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
    Pointer,
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
    inherit_references = False

    def setUp(self):
        Type.reg = {}
        Header.reg = {}
        add_base_types()

    def test(self):
        for file_, content in self.files:
            kw = {}
            if isinstance(file_, Header):
                kw["inherit_references"] = self.inherit_references
            sf = file_.generate(**kw)

            if SAVE_CHUNK_GRAPH:
                sf.gen_chunks_gv_file(
                    join(verbose_dir, file_.path + ".chunks.gv")
                )

            sio = StringIO()
            sf.generate(sio)
            gen_content = sio.getvalue()

            if MODEL_VERBOSE:
                with open(join(verbose_dir, file_.path), "w") as f:
                    f.write(gen_content)

            self._compare_content(content, gen_content)

    def _compare_content(self, expected, generated):
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
        for file_, content in self.files:
            sf_first = file_.generate()
            sf_second = file_.generate()

            sio_first = StringIO()
            sio_second = StringIO()

            sf_first.generate(sio_first)
            sf_second.generate(sio_second)

            first_gen_content = sio_first.getvalue()
            second_gen_content = sio_second.getvalue()

            if MODEL_VERBOSE:
                with open(join(verbose_dir, "gen1" + file_.path), "w") as f:
                    f.write(first_gen_content)
                with open(join(verbose_dir, "gen2" + file_.path), "w") as f:
                    f.write(second_gen_content)

            self.assertEqual(first_gen_content, content)
            self.assertEqual(second_gen_content, first_gen_content)


class TestLabelAndGotoGeneration(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestLabelAndGotoGeneration, self).setUp()
        name = type(self).__name__

        src = Source(name.lower() + ".c")

        lbl = Label("begin")
        i = Type["int"]("i")

        src.add_type(
            Function(
                name = "main",
                body = BodyTree()(
                    Declare(i),
                    lbl,
                    OpAssign(i, OpAdd(i, 1)),
                    Goto(lbl)
                )
            )
        )

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
        a.append_field(Pointer(a)("next"))

        b = Structure("B")
        b.append_field(Pointer(a)("next"))

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

        b.append_field(Pointer(a)("ref"))
        a.append_field(Pointer(b)("ref"))

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
        a.append_field(Pointer(a)("next"))

        b = Structure("B")
        b.append_field(Pointer(a)("next"))

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
        hdr.add_type(Macro("QTAIL_ENTRY", args = [ "type" ]))

        struct = Structure("StructA")
        struct.append_fields([
            Type["QTAIL_ENTRY"]("entry",
                macro_initializer = Initializer({ "type":  struct })
            ),
            Pointer(struct)("next")
        ])
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

        i = Type["int"]("i")
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
            Structure("s", Pointer(Type["a"])("next"))
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


class TestRedirectionToDeclaration(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestRedirectionToDeclaration, self).setUp()
        name = type(self).__name__

        private_h = Header("private.h")
        private_h.add_type(Structure("Private"))

        public_h = Header("public.h")
        public_h.add_types([
            Type["Private"].gen_forward_declaration(),
            Function("public_func")
        ])

        private_c = Source("private.c")
        public_func_impl = Type["public_func"].gen_definition()
        private_c.add_type(public_func_impl)

        src = Source(name.lower() + ".c").add_global_variable(
            # It must internally re-direct pointer from type "Private"
            # to "Private.declaration", its forward declaration.
            Pointer(Type["Private"])("handler")
        )
        src.add_type(Pointer(public_func_impl, name = "cb_ptr"))

        src_content = """\
/* %s */

#include "public.h"

typedef void (*cb_ptr)(void);
Private *handler __attribute__((unused));

""" % (name.lower() + ".c")

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
        h.add_type(Enumeration([("EXT", 1)]))

        src = Source(name.lower() + ".c").add_types([
            Enumeration([("ONE", 1)]),
            Enumeration([("TWO", 2)], enum_name = "A"),
            Enumeration([("THREE", 3)], typedef_name = "B"),
            Enumeration([("FOUR", 4)], enum_name = "C", typedef_name ="D")
        ])

        a = Type["int"]("a")
        b = Type["int"]("b")
        c = Type["A"]("c")
        d = Type["B"]("d")
        e = Type["D"]("e")

        src.add_types([
            Function(name = "main", body = BodyTree()(
                Declare(a, b),
                OpAssign(a, Type["EXT"]),
                OpAssign(b, Type["ONE"]),
                Declare(c),
                OpAssign(c, Type["TWO"]),
                Declare(d),
                OpAssign(d, Type["THREE"]),
                Declare(e),
                OpAssign(e, Type["FOUR"])
            ))
        ])

        src_content = """\
/* {} */

#include "enums.h"

enum A {{
    TWO = 2
}};

typedef enum {{
    THREE = 3
}} B;

typedef enum C {{
    FOUR = 4
}} D;

enum {{
    ONE = 1
}};

void main(void)
{{
    int a, b;
    a = EXT;
    b = ONE;
    enum A c;
    c = TWO;
    B d;
    d = THREE;
    D e;
    e = FOUR;
}}

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


class TestGlobalHeadersInclusion(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestGlobalHeadersInclusion, self).setUp()
        name = type(self).__name__

        hg = Header("global_types.h", is_global = True)
        hl = Header("local_types.h")

        hg.add_type(Type("GT", incomplete = False))
        hl.add_type(Type("LT", incomplete = False))

        hdr = Header(name.lower() + ".h").add_type(
            Structure("Fields", Type["GT"]("f1"), Type["LT"]("f2"))
        )

        hdr_content = """\
/* {path} */
#ifndef INCLUDE_{fname_upper}_H
#define INCLUDE_{fname_upper}_H

#include "local_types.h"

typedef struct Fields {{
    GT f1;
    LT f2;
}} Fields;

#endif /* INCLUDE_{fname_upper}_H */
""".format(path = hdr.path, fname_upper = name.upper())

        src = Source(name.lower() + ".c").add_global_variable(
            Type["Fields"]("fv")
        )

        src_content = """\
/* {} */

#include <global_types.h>
#include "{}"

Fields fv __attribute__((unused));

""".format(src.path, hdr.path)

        self.files = [
            (hdr, hdr_content),
            (src, src_content)
        ]


class TestPointerDereferencing(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestPointerDereferencing, self).setUp()
        name = type(self).__name__

        Pointer(Type["int"], name = "myint")

        src = Source(name.lower() + ".c").add_global_variable(
            Type["myint"]("var")
        )

        src_content = """\
/* {} */

typedef int *myint;
myint var __attribute__((unused));

""".format(src.path)

        self.files = [
            (src, src_content)
        ]


class TestReferencingToSelfDefinedType(SourceModelTestHelper, TestCase):
    inherit_references = True

    def setUp(self):
        super(TestReferencingToSelfDefinedType, self).setUp()
        name = type(self).__name__

        hdr = Header(name.lower() + ".h")
        m = Macro("M_OTHER_TYPE", text = "int")
        hdr.add_type(m)

        ht = Header("macro_types.h")
        ht.add_type(Macro("M_TYPE", text = "M_OTHER_TYPE"))
        ht.add_reference(m)

        hdr.add_global_variable(Type["M_TYPE"]("var"))

        hdr_content = """\
/* {path} */
#ifndef INCLUDE_{fname_upper}_H
#define INCLUDE_{fname_upper}_H

#define M_OTHER_TYPE int

#include "macro_types.h"

extern M_TYPE var;
#endif /* INCLUDE_{fname_upper}_H */
""".format(path = hdr.path, fname_upper = name.upper())

        self.files = [
            (hdr, hdr_content)
        ]


class TestOpaqueCode(SourceModelTestHelper, TestCase):

    def setUp(self):
        super(TestOpaqueCode, self).setUp()

        name = type(self).__name__

        hdr = Header(name.lower() + ".h", protection = False)

        test_var = Type["int"]("test_var")
        test_func = Function(name = "test_func")

        opaque_top = OpaqueCode("""\
/* Generic comment above macros */
"""         ,
            weight = 0
        )

        opaque_bottom = OpaqueCode("""
/* A comment at bottom of file */
"""         ,
            weight = 10
        )

        opaque_middle = OpaqueCode("""
/* How to use test_var and test_func. */

""",
            used_variables = [test_var],
            used_types = [test_func]
            # Default weight (5)
        )

        hdr.add_types([
            # Yields #define statement with weight 1
            Macro("TEST_MACRO"),
            # Yields function declaration with weight 6
            Function(name = "another_test_func"),

            opaque_middle,
            opaque_bottom,
            opaque_top
        ])

        hdr_content = """\
/* {path} */

/* Generic comment above macros */

#define TEST_MACRO

extern int test_var;
void test_func(void);

/* How to use test_var and test_func. */

void another_test_func(void);

/* A comment at bottom of file */
""".format(
            path = hdr.path
        )

        self.files = [
            (hdr, hdr_content)
        ]


if __name__ == "__main__":
    main()
