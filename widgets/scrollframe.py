__all__ = [
    "add_scrollbars"
  , "add_scrollbars_native"
  , "add_scrollbars_with_tags"
]


from six.moves.tkinter import (
    VERTICAL,
    HORIZONTAL,
    ALL,
    Scrollbar,
    Canvas
)
from itertools import (
    count
)
from sys import (
    stderr
)
from platform import (
    system
)


def add_scrollbars_native(outer, inner, row = 0, column = 0):
    "Adds scroll bars to a widget which supports them natively."
    outer.rowconfigure(row + 1, weight = 0)
    outer.columnconfigure(column + 1, weight = 0)

    h_sb = Scrollbar(outer,
        orient = HORIZONTAL,
        command = inner.xview
    )
    h_sb.grid(row = row + 1, column = column, sticky = "NESW")

    v_sb = Scrollbar(outer,
        orient = VERTICAL,
        command = inner.yview
    )
    v_sb.grid(row = row, column = column + 1, sticky = "NESW")

    inner.configure(xscrollcommand = h_sb.set, yscrollcommand = v_sb.set)

    return h_sb, v_sb


def add_scrollbars(outer, InnerType, *inner_args, **kw):
    """ Creates widget of type `InnerType` inside `outer` widget and adds
vertical and horizontal scroll bars for created widget.

:param kw:
    those arguments are passed to `InnerType` constructor except for:

    - row/column: `grid` coordinates inside `outer` (default: 0)
    - inner_kw: see below

    To pass same named arguments to `InnerType` wrap them into a `dict` and
pass it with name "inner_kw" in "kw".
    """

    row, column = kw.pop("row", 0), kw.pop("column", 0)

    kw.update(kw.pop("inner_kw", {}))

    outer.rowconfigure(row, weight = 1)
    outer.rowconfigure(row + 1, weight = 0)
    outer.columnconfigure(column, weight = 1)
    outer.columnconfigure(column + 1, weight = 0)

    # container for inner frame, it supports scrolling
    canvas = Canvas(outer, width = 1, height = 1)
    canvas.grid(row = row, column = row, sticky = "NESW")

    inner = InnerType(canvas, *inner_args, **kw)

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
                h_sb.grid(row = row + 1, column = column, sticky = "NESW")
                h_sb._visible = True

        if inner_h <= cnv_h:
            if v_sb._visible:
                v_sb.grid_forget()
                v_sb._visible = False
        else:
            if not v_sb._visible:
                v_sb.grid(row = row, column = column + 1, sticky = "NESW")
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

    return inner


OS = system()
tags_count = count(0)


def add_scrollbars_with_tags(outer, InnerType, *inner_args, **inner_kw):
    """ Wrapper around `add_scrollbars`. Returns tuple of InnerType instance
and scroll tag. Scroll tag should be added to all `inner` child widgets that
affect scrolling.
    """

    scrolltag = "tag_" + str(next(tags_count))

    inner = add_scrollbars(outer, InnerType, *inner_args, **inner_kw)
    inner.bindtags((scrolltag, ) + inner.bindtags())

    canvas = inner.master

    if OS == "Linux" :
        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview("scroll", -1, "units")
            elif event.num == 5:
                canvas.yview("scroll", 1, "units")

        inner.bind_class(scrolltag,
            "<ButtonPress-4>", _on_mousewheel, '+'
        )
        inner.bind_class(scrolltag,
            "<ButtonPress-5>", _on_mousewheel, '+'
        )

    elif OS == "Windows":
        def _on_mousewheel(event):
            canvas.yview("scroll", -event.delta // 120, "units")

        inner.bind_class(scrolltag,
            "<MouseWheel>", _on_mousewheel, '+'
        )

    else:
        stderr.write("add_scrollbars_with_tags: OS %s not supported" % (OS))


    return inner, scrolltag
