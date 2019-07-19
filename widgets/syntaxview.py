__all__ = [
    "ExText"
      , "SyntaxView"
]

from common import (
    pypath
)
with pypath("..ply"):
    from ply.helpers import (
        iter_tokens
    )
from .gui_frame import (
    GUIFrame
)
from six.moves import (
    range
)
from six.moves.tkinter import (
    HORIZONTAL,
    END,
    Text,
    Scrollbar
)
from six.moves.tkinter_font import (
    NORMAL
)

main_font = ("Courier", 10, NORMAL)
# Note that using ITALIC style results in different line height and
# misalignment between line numbers text and main text
ignored_font = ("Courier", 10, NORMAL)


def decorate_ignored(c):
    if c == " ":
        return u"\u00B7"
    elif c == "\t":
        return u"\u00BB   "
    elif c == "\n":
        return u"\u2193\n"
    else:
        return c


class ExText(GUIFrame):

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.rowconfigure(1, weight = 0)
        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)
        self.columnconfigure(2, weight = 0)

        # line numbers
        self.ln = ln = Text(self,
            font = main_font,
            wrap = "none",
            background = "#BBBBBB",
            width = 4
        )
        ln.grid(row = 0, column = 0, sticky = "NESW")

        # the text itself
        self.text = text = Text(self, font = main_font, wrap = "none")
        text.grid(row = 0, column = 1, sticky = "NESW")

        self.sbv = sbv = Scrollbar(self)
        sbv.grid(row = 0, column = 2, sticky = "NESW")

        sbh = Scrollbar(self, orient = HORIZONTAL)
        sbh.grid(row = 1, column = 0, sticky = "NESW", columnspan = 2)

        sbv.config(command = self._yview)
        text.config(yscrollcommand = self._text_yset)
        ln.config(yscrollcommand = self._ln_yset)

        sbh.config(command = text.xview)
        text.config(xscrollcommand = sbh.set)

    # https://stackoverflow.com/questions/32038701/python-tkinter-making-two-text-widgets-scrolling-synchronize
    def _yview(self, *a):
        self.text.yview(*a)
        self.ln.yview(*a)# https://stackoverflow.com/questions/32038701/python-tkinter-making-two-text-widgets-scrolling-synchronize

    def _text_yset(self, *a):
        self.sbv.set(*a)
        self.ln.yview("moveto", a[0])

    def _ln_yset(self, *a):
        self.sbv.set(*a)
        self.text.yview("moveto", a[0])

    def insert(self, index, text, *tags):
        "See Tkinter Text for arguments description."

        text = self.text
        text.insert(index, text, *tags)

        ln = self.ln
        cur_lines = int(ln.index(END).split('.', 1)[1])
        need_lines = int(text.index(END).split('.', 1)[1])

        if cur_lines >= need_lines:
            return

        ln.insert(END,
            "\n".join(str(l) for l in range(cur_lines + 1, need_lines + 1))
        )


class SyntaxView(ExText):

    def __init__(self, *a, **kw):
        ExText.__init__(self, *a, **kw)

        text = self.text

        text.tag_config("ignored", font = ignored_font, foreground = "#AAAAAA")
        text.tag_config("keyword", foreground = "#FF0000")
        text.tag_config("int", foreground = "#00AAFF")
        text.tag_config("float", foreground = "#00AAFF")
        text.tag_config("char", foreground = "#00AAFF")
        text.tag_config("string", foreground = "#AA8800")
        text.tag_config("id", foreground = "#00AAAA")

    def append_syntax_tree(self, tree, ignored_suffix = ""):
        for t in iter_tokens(tree):
            if t.prefix:
                content = ""
                for c in t.prefix:
                    content += decorate_ignored(c)

                self.insert(END, content, "ignored")

            tags = getattr(t, "tags", [])
            self.insert(END, t.value, *tags)

        for c in ignored_suffix:
            self.insert(END, decorate_ignored(c), "ignored")

