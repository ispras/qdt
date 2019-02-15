from unittest import (
    TestCase,
    main
)
from common import (
    ML,
    mlget as _
)
from six.moves.tkinter import (
    Tk
)


class MLTest(TestCase):

    def setUp(self):
        # A Tk context is required because `StringVar` is used internally.
        Tk()

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


if __name__ == "__main__":
    main()
