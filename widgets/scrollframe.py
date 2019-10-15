__all__ = [
    "add_scrollbars"
# If there is a widget with mouse wheel support then `add` it
# to `WHEELED_WIDGETS` `set`.
  , "WHEELED_WIDGETS"
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
from six.moves.tkinter_ttk import (
    Sizegrip
)
from common import (
    bind_all_mouse_wheel
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


def add_scrollbars_native(outer, inner, row = 0, column = 0, sizegrip = False):
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

    if sizegrip:
        sg = Sizegrip(outer)
        sg.grid(
            row = row + 1,
            column = column + 1,
            sticky = "NESW"
        )
    else:
        sg = None

    return h_sb, v_sb, sg


# widgets reacting on mouse wheel
WHEELED_WIDGETS = set(["TCombobox", "Scrollbar", "Text"])

def add_scrollbars(outer, InnerType, *inner_args, **kw):
    """ Creates widget of type `InnerType` inside `outer` widget and adds
vertical and horizontal scroll bars for created widget.

:param kw:
    those arguments are passed to `InnerType` constructor except for:

    - row/column: `grid` coordinates inside `outer` (default: 0)
    - wheel: support wheel scrolling when mouse is over inner widget
        (default: False)
    - inner_kw: see below

    To pass same named arguments to `InnerType` wrap them into a `dict` and
pass it with name "inner_kw" in "kw".
    """

    row, column = kw.pop("row", 0), kw.pop("column", 0)
    wheel = kw.pop("wheel", False)

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

    if not wheel:
        return inner

    def on_wheel(e):
        w = e.widget

        # Is the `w`idget our inner?
        m = w
        while m is not None:
            if m is inner:
                break
            m = m.master
        else:
            # Outer widget
            return

        cls = w.winfo_class()

        if cls in WHEELED_WIDGETS:
            # When mouse pointer is over `WHEELED_WIDGETS` the canvas
            # must not be scrolled. But there are few exceptions for
            # convenience.
            try:
                a, b = w.yview()
            except:
                # not all "wheeled" widgets provides `yview` and those values
                # prevents heuristics about fully scrolled `w`idgets below.
                a, b = None, None

            if e.delta > 0:
                if a == 0.0:
                    pass # w is fully scrolled up
                elif w.winfo_rooty() < canvas.winfo_rooty():
                    pass # user does not see upper border of w
                    # XXX: we also have to prevent scrolling of `w` but
                    # returning "break" does not work.
                else:
                    return
            elif e.delta < 0:
                if b == 1.0:
                    pass # w is fully scrolled down
                elif (w.winfo_rooty() + w.winfo_height() >
                    canvas.winfo_rooty() + canvas.winfo_height()
                ):
                    pass # user does not see bottom border of w
                else:
                    return
            else:
                return

        canvas.yview("scroll", -e.delta, "units")

    bind_all_mouse_wheel(inner, on_wheel, "+")

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
