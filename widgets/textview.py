__all__ = [
    "SearchWindow"
  , "TextViewerTk"
  , "TextViewerToplevel"
]

from common import (
    ee,
    LineNoStream,
    mlget as _,
    notifier,
)
from .gui_frame import (
    GUIFrame,
)
from .gui_tk import (
    GUITk,
)
from .gui_toplevel import (
    GUIToplevel,
)
from .hotkey import (
    HKEntry,
)
from .scrollframe import (
    add_scrollbars_native,
)
from .statusbar import (
    Statusbar,
)
from .text_canvas import (
    TextCanvas,
)
from .tk_geometry_helper import (
    centrify_tk_window,
    TkGeometryHelper,
)
from .var_widgets import (
    VarButton,
    VarCheckbutton,
    VarLabel,
)

from six.moves.tkinter import (
    BooleanVar,
    StringVar,
)
from six.moves.tkinter_ttk import (
    Sizegrip,
)


DEBUG = ee("DEBUG_TEXTVIEW", "False")
DEBUG_STREAM_SIZE = 100001


@notifier(
    "find_next", # pattern, as regular expression
)
class SearchWindow(GUIToplevel, TkGeometryHelper):

    def __init__(self, *a, **kw):
        GUIToplevel.__init__(self, *a, **kw)

        self.title(_("Search"))
        self.topmost = True

        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)

        row = 0; self.rowconfigure(row, weight = 0)

        VarLabel(self, text = _("Find")).grid(
            row = row,
            column = 0,
            sticky = "NE",
        )
        self._pattern_var = var = StringVar(self)
        self._e_pattern = e = HKEntry(self, textvariable = var)
        e.grid(
            row = row,
            column = 1,
            sticky = "NEW",
        )

        row += 1; self.rowconfigure(row, weight = 0)
        self._re_var = var = BooleanVar(self)
        VarCheckbutton(self,
            variable = var,
            text = _("Regular expression")
        ).grid(
            row = row,
            column = 0,
            columnspan = 2,
            sticky = "NW",
        )

        row += 1; self.rowconfigure(row, weight = 0)
        fr_buttons = GUIFrame(self)
        fr_buttons.grid(
            row = row,
            column = 0,
            columnspan = 2,
            sticky = "NE",
        )

        fr_buttons.rowconfigure(0, weight = 0)

        bt_col = 0; fr_buttons.columnconfigure(bt_col, weight = 0)
        VarButton(fr_buttons,
            text = _("Find/Next (Enter)"),
            command = self._on_find_next,
        ).grid(
            row = 0,
            column = bt_col,
            sticky = "NE",
        )

        self.bind("<Return>", self._on_return) # Enter
        self.bind("<Enter>", self._on_enter, "+") # mouse pointer enter

        self._had_focus = False
        self.bind("<FocusIn>", self._on_focus_in, "+")
        self.bind("<FocusOut>", self._on_focus_out, "+")

        self.bind("<Escape>", self._on_escape)
        self.protocol("WM_DELETE_WINDOW", self._on_delete_window)

        self.resizable(True, False)

    def _on_delete_window(self):
        self.withdraw()

    def _on_escape(self, __):
        self.withdraw()

    def _on_focus_in(self, e):
        if e.widget is self:
            if not self._had_focus:
                self._had_focus = True
                self._e_pattern.focus_set()

    def _on_focus_out(self, e):
        if e.widget is self:
            self._had_focus = False

    def _on_enter(self, __):
        if not self._had_focus:
            self.focus_set()

    def _on_return(self, __):
        self._on_find_next()
        return "break"

    def _on_find_next(self):
        self.__notify_find_next(self._pattern_var.get(), self._re_var.get())


class _TextViewerWindow(object):

    def __init__(self):
        file_name = StringVar(self)

        self.title(_("%s - Text Viewer") % file_name)

        hk = self.hk
        hk(self._search, 41,
           description = "Show search window",
           symbol = "F",
        )

        self.columnconfigure(0, weight = 1)
        self.columnconfigure(1, weight = 0)

        row = 0; self.rowconfigure(row, weight = 1)
        self._text = text = TextCanvas(self)
        text.grid(row = row, column = 0, sticky = "NESW")

        add_scrollbars_native(self, text, row = row)
        row += 1 # horizontal scroll bar

        row += 1; self.rowconfigure(row, weight = 0)
        sb = Statusbar(self)
        sb.grid(row = row, column = 0, sticky = "NESW")

        Sizegrip(self).grid(row = row, column = 1, sticky = "NESW")

        sb.right(_("%s/%s") % (text._var_lineno, text._var_total_lines))

        self._file_name = file_name

        text.focus_set()

        self._sw = sw = SearchWindow(self)
        sw.withdraw()
        sw.watch_find_next(self._find_next)

    @property
    def lineno(self):
        return self._text.lineno

    @lineno.setter
    def lineno(self, lineno):
        self._text.lineno = lineno

    def _find_next(self, pattern, as_regexp):
        print(pattern, as_regexp)

    def _search(self):
        sw = self._sw
        sw.deiconify()
        sw.focus_set()
        centrify_tk_window(self, sw)

    @property
    def file_name(self):
        return self._file_name.get()

    @file_name.setter
    def file_name(self, file_name):
        if self._file_name.get() == file_name:
            return
        self._file_name.set(file_name)

        if DEBUG:
            stream = LineNoStream(size = DEBUG_STREAM_SIZE)
        else:
            stream = open(file_name, "rb")

        text = self._text
        text.stream = stream
        self.enqueue(text.co_build_index())


class TextViewerTk(GUITk, _TextViewerWindow):

    def __init__(self, **kw):
        GUITk.__init__(self, **kw)
        _TextViewerWindow.__init__(self)


class TextViewerToplevel(GUIToplevel, _TextViewerWindow):

    def __init__(self, master, **kw):
        GUIToplevel.__init__(self, master, **kw)
        _TextViewerWindow.__init__(self)
