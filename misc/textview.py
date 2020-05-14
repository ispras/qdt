from argparse import (
    ArgumentParser,
)
from common import (
    ee,
    LineNoStream,
    mlget as _,
    LineIndex,
    bind_mouse_wheel,
)
from widgets import (
    GUITk,
    Statusbar,
)
from six.moves.tkinter import (
    RIGHT,
    LEFT,
    Canvas,
    IntVar,
    Scrollbar,
    VERTICAL,
    HORIZONTAL,
)
from six.moves.tkinter_ttk import (
    Sizegrip,
)
from six.moves.tkinter_font import (
    Font,
    NORMAL,
    BOLD,
)

DEBUG = ee("DEBUG_TEXTVIEW", "False")
DEBUG_STREAM_SIZE = 100000


class TextViewerWindow(GUITk, object):

    def __init__(self):
        GUITk.__init__(self)
        self.title(_("Text Viewer"))

        self.columnconfigure(0, weight = 1)
        self.columnconfigure(1, weight = 0)

        row = 0
        self.rowconfigure(row, weight = 1)

        self._text = text = Canvas(self,
            background = "white",
        )
        text.bind("<Configure>", self._on_text_configure, "+")
        text.grid(row = row, column = 0, sticky = "NESW")
        bind_mouse_wheel(text, self._on_mouse_wheel)

        self._vsb = vsb = Scrollbar(self,
            orient = VERTICAL,
            command = self.yview,
        )
        vsb.grid(row = row, column = 1, sticky = "NESW")

        row += 1; self.rowconfigure(row, weight = 0)
        self._hsb = hsb = Scrollbar(self,
            orient = HORIZONTAL,
            command = text.xview
        )
        text.configure(xscrollcommand = hsb.set)
        hsb.grid(row = row, column = 0, sticky = "NESW")

        row += 1; self.rowconfigure(row, weight = 0)
        sb = Statusbar(self)
        sb.grid(row = row, column = 0, sticky = "NESW")

        Sizegrip(self).grid(row = row, column = 1, sticky = "NESW")

        self._var_total_lines = total_var = IntVar(self)
        total_var.set(0)
        # Contains showed line number. It's one more then internally used
        # line index.
        self._var_lineno = lineno_var = IntVar(self)
        lineno_var.set(1)
        sb.right(_("%s/%s") % (lineno_var, total_var))

        # TODO: make it configarable
        fonts = [
            Font(font = ("Courier", 10, NORMAL)),
            Font(font = ("Courier", 10, BOLD)),
        ]
        self._main_font, self._lineno_font = fonts
        self._linespace = max(f.metrics("linespace") for f in fonts)
        self._ylinepadding = 0 # 1
        self._lineno_pading = 10

        self._file_name = None
        self._page_size = 100

    def _on_mouse_wheel(self, e):
        if e.delta > 0:
            self._yview_scroll(-5, "units")
        elif e.delta < 0:
            self._yview_scroll(5, "units")
        return "break"

    @property
    def page_size_f(self):
        return float(self._page_size)

    @property
    def total_lines(self):
        return self._var_total_lines.get()

    @property
    def total_lines_f(self):
        return float(self.total_lines)

    @property
    def lineno(self):
        return self._var_lineno.get()

    @property
    def lineidx(self):
        return self.lineno - 1

    @lineno.setter
    def lineno(self, lineno_raw):
        lineno = max(1, min(self.total_lines, lineno_raw))

        var_lineno = self._var_lineno
        if lineno == var_lineno.get():
            return
        var_lineno.set(lineno)

        self.draw()
        self._update_vsb()

    def draw(self):
        # cache some values
        lineidx = self.lineidx
        lineno_font = self._lineno_font
        main_font = self._main_font
        lineno_pading = self._lineno_pading
        linespace = self._linespace

        if DEBUG:
            stream = LineNoStream(size = DEBUG_STREAM_SIZE)
        else:
            stream = open(self._file_name, "rb")

        # read two chunks
        citer = self._index.iter_chunks(stream, lineidx)
        blob, start_line = next(citer)
        try:
            blob += next(citer)[0]
        except StopIteration:
            # EOF
            pass

        stream.close()

        text = self._text
        # clear
        text.delete(*text.find_all())

        lines = list(blob.decode("unicode_escape").splitlines())

        # space for line numbers
        xshift = lineno_font.measure(str(start_line + len(lines)))

        yshift = -(lineidx - start_line) * linespace
        yinc = linespace + self._ylinepadding

        view_height = text.winfo_height()
        x = xshift
        y = self._ylinepadding + yshift

        for cur_lineno, line in enumerate(lines,
            start_line + 1 # conventionally, line enumeration starts from 1
        ):
            if -linespace < y and y < view_height:
                text.create_text(x, y,
                    text = cur_lineno,
                    justify = RIGHT,
                    anchor = "ne",
                    font = lineno_font,
                    fill = "#aaaaaa",
                )
                text.create_text(x + lineno_pading, y,
                    text = line,
                    justify = LEFT,
                    anchor = "nw",
                    font = main_font,
                )

            y += yinc

    def _on_text_configure(self, __):
        self.draw()

    def yview(self, *a):
        getattr(self, "_yview_" + a[0])(*a[1:])

    def _yview_moveto(self, offset):
        offset_f = float(offset)
        lineno_f = self.total_lines_f * offset_f
        self.lineno = int(lineno_f)

    def _yview_scroll(self, step, unit):
        step_i = int(step)
        if unit == "pages":
            shift = step_i * self._page_size
        elif unit == "units": # lines
            shift = step_i
        else:
            raise ValueError("Unsupported scsroll unit: " + unit)

        self.lineno += shift

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        if self._file_name == file_name:
            return
        self._file_name = file_name
        self._index = None # invalidate old index

        self.enqueue(self.co_build_index())

    def co_build_index(self):
        ubd = self._update_total_lines

        self._index = index = LineIndex()

        if DEBUG:
            stream = LineNoStream(size = DEBUG_STREAM_SIZE)
        else:
            stream = open(self._file_name, "rb")

        try:
            co_index_builder = index.co_build(stream)

            # update view while just indexed lines can be visible
            for __ in co_index_builder:
                current_lines = index.current_lines
                yield True
                ubd(current_lines)
                self.draw()
                if current_lines > self.lineno + self._page_size:
                    break

            for ready in co_index_builder:
                ubd(index.current_lines)
                yield ready
        finally:
            stream.close()

        ubd(index.total_lines)

    def _update_total_lines(self, val):
        self._var_total_lines.set(val)
        self._update_vsb()

    def _update_vsb(self):
        total_lines_f = self.total_lines_f
        try:
            lo = float(self.lineno) / total_lines_f
            hi = lo + self.page_size_f / total_lines_f
        except ZeroDivisionError:
            lo = 0.0
            hi = 1.0
        self._vsb.set(lo, hi)


def main():
    ap = ArgumentParser(
        description = "A Text Viewer",
    )
    ap.add_argument("file_name")

    args = ap.parse_args()

    w = TextViewerWindow()
    w.file_name = args.file_name
    w.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
