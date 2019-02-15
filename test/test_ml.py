from unittest import (
    TestCase,
    main
)
from common import (
    ML,
    mlget as _
)
from six.moves.tkinter import (
    StringVar,
    Tk
)
from common import (
    FormatedStringVar,
    FormatVar
)


class FSVTestBase(TestCase):

    def setUp(self):
        # A Tk context is required because `StringVar` is used internally.
        Tk()


class MLTest(FSVTestBase):

    def setUp(self):
        super(MLTest, self).setUp()
        ML.set_language("ru_RU.utf-8")

    def test_format_with_unicode(self):
        """ Under Py2 formatting a `str` which contains encoded unicode with an
explicit `unicode` value results in an `UnicodeDecodeError`.
        """
        fmt = _("Create %s (%d) of type '%s'.")
        kind = _("system bus device")
        _id = 0xdeadbeef
        qtype = u"something"

        fmt % (kind, _id, qtype)


class FSVTest(FSVTestBase):

    def test_auto_reformat(self):
        fmt = FormatVar(value = "Text is '%s'")
        text = StringVar(value = "[ a text will be here ]")
        res = fmt % text

        self.assertIsInstance(res, FormatedStringVar)

        self.assertEqual(res.get(), "Text is '[ a text will be here ]'")

        def on_w(*__):
            val = res.get()
            # print("New value: %s" % val)
            self._cur_val = val

        res.trace_variable("w", on_w)

        text.set("A text")
        self.assertEqual(self._cur_val, "Text is 'A text'")

        fmt.set("'%s' is text.")
        self.assertEqual(self._cur_val, "'A text' is text.")


if __name__ == "__main__":
    main()
