__all__ = [
    "TextCanvas"
]


from six.moves.tkinter import (
    IntVar,
    Canvas,
    RIGHT,
    LEFT,
)
from six.moves.tkinter_font import (
    Font,
    NORMAL,
    BOLD,
)
from common import (
    bind_mouse_wheel,
    LineIndex,
)


# TextCanvas states
class selecting_started: pass
class selecting: pass

class TextCanvas(Canvas, object):
    """ Shows big raw stream with text.
    """

    def __init__(self, master, **kw):
        kw.setdefault("background", "white")
        self._xscrollcommand = kw.pop("xscrollcommand", None)
        self._yscrollcommand = kw.pop("yscrollcommand", None)
        self._encoding = kw.pop("encoding", "unicode_escape")
        stream = kw.pop("stream", None)

        Canvas.__init__(self, master, **kw)

        self.bind("<Configure>", self._on_configure, "+")
        bind_mouse_wheel(self, self._on_mouse_wheel)

        self.bind("<Enter>", self._on_enter, "+")

        self.bind("<Prior>", self._on_prior, "+") # Page Up
        self.bind("<Next>", self._on_next, "+") # Page Down

        self._var_total_lines = total_var = IntVar(self)
        total_var.set(0)
        # Contains showed line number. It's one greater than internally used
        # index of line.
        self._var_lineno = lineno_var = IntVar(self)
        lineno_var.set(1)

        # TODO: make it configurable
        fonts = [
            Font(font = ("Courier", 10, NORMAL)),
            Font(font = ("Courier", 10, BOLD)),
        ]
        self._main_font, self._lineno_font = fonts
        self._linespace = max(f.metrics("linespace") for f in fonts)
        # Note, padding space is used for selected lines highlighting.
        self._ylinepadding = 1
        self._lineno_pading = 10
        self._page_size = 100 # in lines
        self._page_width = 0 # in Canvas units
        self._x_offset = 0
        self._index = None # index of lines offsets

        self._stream = None
        # trigger the property
        self.stream = stream

        self._state = None

        # Selection is defined by two tuples: (lineidx, charidx)
        self._sel_start = None # first selected char
        self._sel_limit = None # a char immediately after last selected one
        self.selection_threshold = 10

        self.bind("<ButtonPress-1>", self._on_bt1_press, "+")
        self.bind("<ButtonRelease-1>", self._on_bt1_release, "+")
        self.bind("<Motion>", self._on_motion, "+")

    @property
    def stream(self):
        return self._stream

    @stream.setter
    def stream(self, stream):
        if self._stream is not None:
            raise NotImplementedError("Cannot change stream")
        self._stream = stream

    def co_build_index(self):
        stream = self._stream
        if stream is None:
            return

        ubd = self._update_total_lines

        self._index = index = LineIndex()

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

        ubd(index.total_lines)

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
    def lineidx(self):
        return self.lineno - 1

    @property
    def lineno(self):
        return self._var_lineno.get()

    @lineno.setter
    def lineno(self, lineno_raw):
        lineno = max(1, min(self.total_lines, lineno_raw))

        var_lineno = self._var_lineno
        if lineno == var_lineno.get():
            return
        var_lineno.set(lineno)

        self.draw()
        self._update_vsb()

    @property
    def x_offset(self):
        return self._x_offset

    @x_offset.setter
    def x_offset(self, x_offset):
        limit = self._max_text_width - self._page_width
        x_offset = max(0, min(limit, x_offset))

        if x_offset == self._x_offset:
            return
        self._x_offset = x_offset

        self.draw()

    def configure(self, **kw):
        if "xscrollcommand" in kw:
            self._xscrollcommand = kw.pop("xscrollcommand")
        if "yscrollcommand" in kw:
            self._yscrollcommand = kw.pop("yscrollcommand")
        if kw:
            Canvas.configure(self, **kw)

    config = configure

    def xview(self, *a):
        getattr(self, "_xview_" + a[0])(*a[1:])

    def _xview_moveto(self, offset):
        offset_f = float(offset)
        self.x_offset = int(offset_f * float(self._max_text_width))

    def _xview_scroll(self, step, unit):
        step_i = int(step)
        if unit == "pages":
            shift = step_i * self._page_width
        elif unit == "units": # canvas coordinates
            shift = step_i
        else:
            raise ValueError("Unsupported scsroll unit: " + unit)

        self.x_offset += shift

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

    def draw(self):
        # clear
        self.delete(*self.find_all())

        stream = self._stream
        if stream is None:
            # stream with text is not set
            return

        index = self._index
        if index is None:
            # lines offsets index is not built
            return

        # cache some values
        lineidx = self.lineidx
        lineno_font = self._lineno_font
        main_font = self._main_font
        main_font_measure = main_font.measure
        ylinepadding = self._ylinepadding

        # read two chunks
        citer = index.iter_chunks(stream, lineidx)
        blob, start_line = next(citer)
        try:
            blob += next(citer)[0]
        except StopIteration:
            # EOF
            pass

        lines = list(blob.decode(self._encoding).splitlines())

        # if last line in the stream has new line suffix, show empty new line
        if blob.endswith(b"\r") or blob.endswith(b"\n"):
            # Note, `splitlines` drops last empty line while `total_lines`
            # accounts it.
            if start_line + len(lines) + 1 == self.total_lines:
                lines.append(u"")

        lines_offset = lineidx - start_line
        picked_lines = lines[lines_offset:]

        # conventionally, line enumeration starts from 1
        cur_lineno = lineidx + 1

        # space for line numbers
        lineno_width = lineno_font.measure(str(cur_lineno + len(picked_lines)))

        lineno_end_x = lineno_width + self._lineno_pading
        text_start_x = lineno_end_x - self._x_offset

        lines_width = []

        # y coordinate iteration parameters
        view_height = self.winfo_height()
        y_start = ylinepadding
        y = y_start
        y_inc = self._linespace + ylinepadding

        # place opaque rectangle below line numbers and above main text
        self.create_rectangle(
            0, 0, lineno_end_x, view_height,
            fill = "grey",
            outline = "white",
        )

        # cache
        create_text = self.create_text
        lower = self.lower

        for cur_lineno, line in enumerate(picked_lines, cur_lineno):
            if view_height <= y:
                break

            create_text(lineno_end_x, y,
                text = cur_lineno,
                justify = RIGHT,
                anchor = "ne",
                font = lineno_font,
                fill = "white",
            )
            line_iid = create_text(text_start_x, y,
                text = line,
                justify = LEFT,
                anchor = "nw",
                font = main_font,
            )
            lower(line_iid)

            lines_width.append(main_font_measure(line))

            y += y_inc

        sel_start = self._sel_start

        # Selected lines highlighting.
        # It's not a loop actually.
        # This magic is used to prevent nested `if`s using `break`.
        while sel_start is not None:
            ss_l, ss_c = sel_start
            sl_l, sl_c = self._sel_limit

            if ss_l < lineidx:
                ss_l = lineidx
                ss_c = 0

                if sl_l < ss_l:
                    # selected block is above visible lines
                    break

            first_line_idx = ss_l - lineidx

            # highlighting is underlining
            y = y_start + first_line_idx * y_inc + y_inc - ylinepadding
            if view_height <= y:
                # selected block is below visible lines
                break

            first_line = picked_lines[first_line_idx]

            # cache
            create_line = self.create_line

            # first selected line is highlighted from first selected character
            sel_start_x = text_start_x + main_font_measure(first_line[:ss_c])
            try:
                if ss_l == sl_l:
                    # only one line is selected
                    sel_end_x = text_start_x + \
                        main_font_measure(first_line[:sl_c])
                    break
                else:
                    sel_end_x = text_start_x + lines_width[first_line_idx]
            finally:
                lower(create_line(sel_start_x, y, sel_end_x, y))

            y += y_inc

            # intermediate selected lines are fully highlighted
            last_line_idx = sl_l - lineidx
            for width in lines_width[first_line_idx + 1:last_line_idx]:
                if view_height <= y:
                    break
                lower(create_line(text_start_x, y, text_start_x + width, y))
                y += y_inc

            else:
                # last selected line is highlighted to last selected char
                last_line = picked_lines[last_line_idx]
                sel_end_x = text_start_x + main_font_measure(last_line[:sl_c])
                lower(create_line(text_start_x, y, sel_end_x, y))

            break

        # update horizontal scrolling
        self._page_width = max(0,
            self.winfo_width() - lineno_width - self._lineno_pading
        )
        self._max_text_width = max(lines_width) if lines_width else 0
        self._update_hsb()

        # update page size
        page_size = (cur_lineno - 1) - lineidx

        if view_height != y:
            # last line is not fully showed
            page_size -= 1

        if self._page_size != page_size:
            self._page_size = page_size
            self._update_vsb()

        # preserve some values
        self._text_start_x = text_start_x
        self._picked_lines = picked_lines
        self._y_start = y_start
        self._y_inc = y_inc

    def _on_configure(self, __):
        self.draw()

    def _on_mouse_wheel(self, e):
        if e.delta > 0:
            self._yview_scroll(-5, "units")
        elif e.delta < 0:
            self._yview_scroll(5, "units")
        return "break"

    def _update_hsb(self):
        cmd = self._xscrollcommand
        if cmd is None:
            return

        max_text_width = self._max_text_width
        if max_text_width == 0:
            lo, hi = 0., 1.
        else:
            max_text_width_f = float(max_text_width)
            lo = float(self._x_offset) / max_text_width_f
            page_width_f = float(self._page_width)
            hi = lo + page_width_f / max_text_width_f

        cmd(lo, hi)

    def _update_total_lines(self, val):
        self._var_total_lines.set(val)
        self._update_vsb()

    def _update_vsb(self):
        cmd = self._yscrollcommand
        if cmd is None:
            return

        total_lines_f = self.total_lines_f
        try:
            lo = float(self.lineno) / total_lines_f
            hi = lo + self.page_size_f / total_lines_f
        except ZeroDivisionError:
            lo = 0.0
            hi = 1.0

        cmd(lo, hi)

    def _on_enter(self, __):
        self.focus_set()

    def _on_prior(self, __):
        self._yview_scroll(-1, "pages")

    def _on_next(self, __):
        self._yview_scroll(1, "pages")

    def _lineidx_charidx(self, x, y):
        # cache
        picked_lines = self._picked_lines

        x -= self._text_start_x

        # get line index
        rel_lineidx = (y - self._y_start) // self._y_inc

        if x < 0:
            # map to last character in previous line
            rel_lineidx -= 1

        lineidx = self.lineidx + rel_lineidx

        # get char index
        try:
            line = picked_lines[rel_lineidx]
        except IndexError:
            # _lineidx_charidx is only used for x, y of mouse pointer.
            # So, there are two cases:
            # 1. EOF is visible
            # 2. a very very tall display
            return (
                self.lineidx + len(picked_lines) - 1,
                len(picked_lines[-1])
            )

        # bisect is used to support for non-monospaced fonts, e.g. Serif.
        right = len(line)

        if x < 0:
            return (lineidx, right)

        # Allow to select character right after last one in the line
        # Note, result is in range [0, {initial `right` value}).
        right += 1

        left = 0
        measure = self._main_font.measure

        while True:
            mid = (left + right) >> 1
            if x < measure(line[:mid]):
                if right == mid:
                    break
                right = mid
            else:
                if left == mid:
                    break
                left = mid

        charidx = mid

        return (lineidx, charidx)

    def _on_bt1_press(self, e):
        if self._state is not None:
            return
        if self._sel_start is not None:
            self._sel_start = self._sel_limit = None
            self.draw()

        self._state = selecting_started
        self._sel_start_point = e.x, e.y

    def _on_bt1_release(self, __):
        if self._state is selecting_started:
            del self._sel_start_point
            self._state = None
        elif self._state is selecting:
            self._state = None
            del self._sel_first

    def _on_motion(self, e):
        x, y = e.x, e.y

        do_selecting = False

        if self._state is selecting_started:
            sx, sy = self._sel_start_point
            if abs(sx - x) + abs(sy - y) > self.selection_threshold:
                self._sel_first = self._lineidx_charidx(sx, sy)
                self._state = selecting
                del self._sel_start_point
                do_selecting = True
        elif self._state is selecting:
            do_selecting = True

        if do_selecting:
            first = self._sel_first
            lineidx, charidx = self._lineidx_charidx(x, y)
            if lineidx < first[0]:
                self._sel_start = (lineidx, charidx)
                self._sel_limit = first
            else:
                self._sel_start = first
                self._sel_limit = (lineidx, charidx + 1)
            self.draw()
