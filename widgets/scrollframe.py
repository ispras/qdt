__all__ = [
    "add_scrollbars"
  , "add_scrollbars_native"
]


from six.moves.tkinter import (
    VERTICAL,
    HORIZONTAL,
    ALL,
    Scrollbar,
    Canvas
)
from platform import (
    system
)
OS = system()


def add_scrollbars_native(outer, inner,
        row = 0,
        column = 0,
        rowspan = 1,
        columnspan = 1
    ):
    "Adds scroll bars to a widget which supports them natively."
    outer.rowconfigure(row + rowspan, weight = 0)
    outer.columnconfigure(column + columnspan, weight = 0)

    h_sb = Scrollbar(outer,
        orient = HORIZONTAL,
        command = inner.xview
    )
    h_sb.grid(
        row = row + rowspan,
        column = column,
        columnspan = columnspan,
        sticky = "NESW"
    )

    v_sb = Scrollbar(outer,
        orient = VERTICAL,
        command = inner.yview
    )
    v_sb.grid(
        row = row,
        rowspan = rowspan,
        column = column + columnspan,
        sticky = "NESW"
    )

    inner.configure(xscrollcommand = h_sb.set, yscrollcommand = v_sb.set)

    return h_sb, v_sb


def get_mouse_wheel_handler(widget, orient, factor = 1, what = "units"):
    view_command = getattr(widget, orient + 'view')

    if OS == 'Linux':
        def onMouseWheel(event):
            if event.num == 4:
                view_command("scroll", (-1) * factor, what)
            elif event.num == 5:
                view_command("scroll", factor, what)

    elif OS == 'Windows':
        def onMouseWheel(event):
            view_command("scroll",
                (-1) * int((event.delta / 120) * factor),
                what
            )

    return onMouseWheel


class MousewheelSupport(object):
    def __init__(self, root, tag):
        self._active_area = None

        if OS == "Linux" :
            root.bind_class(tag, "<4>", self._on_mousewheel, add ='+')
            root.bind_class(tag, "<5>", self._on_mousewheel, add ='+')
        else:
            # Windows
            root.bind_class(tag, "<MouseWheel>", self._on_mousewheel,
                add = '+'
            )

    def _on_mousewheel(self, event):
        if self._active_area:
            self._active_area.onMouseWheel(event)

    def _mousewheel_bind(self, widget):
        self._active_area = widget

    def _mousewheel_unbind(self, event):
        self._active_area = None

    def add_support_to(self, widget, xscrollbar, yscrollbar,
            what = "units",
            horizontal_factor = 2,
            vertical_factor = 2
        ):

        xscrollbar.onMouseWheel = get_mouse_wheel_handler(
            widget, 'x', horizontal_factor, what
        )
        xscrollbar.bind("<Enter>",
            lambda _: self._mousewheel_bind(xscrollbar)
        )
        xscrollbar.bind("<Leave>", self._mousewheel_unbind)

        yscrollbar.onMouseWheel = get_mouse_wheel_handler(
            widget, 'y', vertical_factor, what
        )
        yscrollbar.bind("<Enter>",
            lambda _: self._mousewheel_bind(yscrollbar)
        )
        yscrollbar.bind("<Leave>", self._mousewheel_unbind)

        widget.bind("<Enter>", lambda _: self._mousewheel_bind(widget))
        widget.bind("<Leave>", self._mousewheel_unbind)
        # set main scrollbar
        widget.onMouseWheel = yscrollbar.onMouseWheel


cur_tag_num = 0


def add_scrollbars(outer, InnerType, *inner_args, **inner_kw):
    """ Creates widget of type `InnerType` inside `outer` widget and adds
vertical and horizontal scroll bars for created widget.
Returns tuple of InnerType instance and scroll tag. Scroll tag should be added
to all widgets that affect scrolling.
    """

    outer.rowconfigure(0, weight = 1)
    outer.rowconfigure(1, weight = 0)
    outer.columnconfigure(0, weight = 1)
    outer.columnconfigure(1, weight = 0)

    # container for inner frame, it supports scrolling
    canvas = Canvas(outer, width = 1, height = 1)
    canvas.grid(row = 0, column = 0, sticky = "NESW")

    inner = InnerType(canvas, *inner_args, **inner_kw)

    inner_id = canvas.create_window((0, 0),
        window = inner,
        anchor = "nw"
    )

    h_sb = Scrollbar(outer,
        orient = "horizontal",
        command = canvas.xview
    )
    h_sb._visible = False

    v_sb = Scrollbar(outer,
        orient = "vertical",
        command = canvas.yview
    )
    v_sb._visible = False

    canvas.configure(xscrollcommand = h_sb.set, yscrollcommand = v_sb.set)

    def scrollbar_visibility():
        "Automatically shows & hides the scroll bar."

        cnv_w, cnv_h = canvas.winfo_width(), canvas.winfo_height()
        inner_w, inner_h = inner.winfo_width(), inner.winfo_height()

        if inner_w <= cnv_w:
            if h_sb._visible:
                h_sb.grid_forget()
                h_sb._visible = False
        else:
            if not h_sb._visible:
                h_sb.grid(row = 1, column = 0, sticky = "NESW")
                h_sb._visible = True

        if inner_h <= cnv_h:
            if v_sb._visible:
                v_sb.grid_forget()
                v_sb._visible = False
        else:
            if not v_sb._visible:
                v_sb.grid(row = 0, column = 1, sticky = "NESW")
                v_sb._visible = True

    def inner_configure(_):
        scrollbar_visibility()
        canvas.configure(
            scrollregion = canvas.bbox(ALL),
            # Require as many space as inner widget do.
            width = inner.winfo_reqwidth(),
            height = inner.winfo_reqheight()
        )

    inner.bind("<Configure>", inner_configure, "+")

    def canvas_configure(e):
        scrollbar_visibility()
        # Get to the inner widget at least desired space.
        # Stretch it when possible.
        canvas.itemconfig(inner_id,
            width = max(e.width, inner.winfo_reqwidth()),
            height = max(e.height, inner.winfo_reqheight())
        )

    canvas.bind("<Configure>", canvas_configure, "+")

    global cur_tag_num
    cur_tag_num += 1
    scrolltag = "tag_" + str(cur_tag_num)

    inner.bindtags((scrolltag,) + inner.bindtags())

    mousewheel_support = MousewheelSupport(outer, scrolltag)
    mousewheel_support.add_support_to(canvas,
        xscrollbar = h_sb,
        yscrollbar = v_sb
    )

    return inner, scrolltag
