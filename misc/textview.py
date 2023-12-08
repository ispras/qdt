from argparse import (
    ArgumentParser,
)
from common import (
    UserSettings,
    ee,
    LineNoStream,
    mlget as _,
)
from widgets import (
    add_scrollbars_native,
    TextCanvas,
    GUITk,
    Statusbar,
)
from six.moves.tkinter_ttk import (
    Sizegrip,
)

DEBUG = ee("DEBUG_TEXTVIEW", "False")
DEBUG_STREAM_SIZE = 100001


class QDTTextViewSettings(UserSettings):

    _suffix = ".qdt_textview_settings.py"

    def __init__(self):
        super(QDTTextViewSettings, self).__init__(
            glob = globals(),
            version = 0.1,
            # default values
            geometry = (600, 800),
        )


class TextViewerWindow(GUITk, object):

    def __init__(self):
        GUITk.__init__(self)
        self.title(_("Text Viewer"))

        self.columnconfigure(0, weight = 1)
        self.columnconfigure(1, weight = 0)

        row = 0
        self.rowconfigure(row, weight = 1)

        self._text = text = TextCanvas(self)
        text.grid(row = row, column = 0, sticky = "NESW")

        add_scrollbars_native(self, text, row = row)
        row += 1 # horizontal scroll bar

        row += 1; self.rowconfigure(row, weight = 0)
        sb = Statusbar(self)
        sb.grid(row = row, column = 0, sticky = "NESW")

        Sizegrip(self).grid(row = row, column = 1, sticky = "NESW")

        sb.right(_("%s/%s") % (text._var_lineno, text._var_total_lines))

        self._file_name = None

        text.focus_set()

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        if self._file_name == file_name:
            return
        self._file_name = file_name

        if DEBUG:
            stream = LineNoStream(size = DEBUG_STREAM_SIZE)
        else:
            stream = open(file_name, "rb")

        text = self._text
        text.stream = stream
        self.enqueue(text.co_build_index())


def main():
    ap = ArgumentParser(
        description = "A Text Viewer",
    )
    ap.add_argument("file_name")

    args = ap.parse_args()

    w = TextViewerWindow()
    w.file_name = args.file_name

    with QDTTextViewSettings() as settings:
        w.set_geometry_delayed(*settings.geometry)

        w.mainloop()

        # only save width and height
        settings.geometry = w.last_geometry[:2]


if __name__ == "__main__":
    exit(main() or 0)
