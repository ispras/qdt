__all__ = [
    "add_scrollbars"
]


from six.moves.tkinter import (
    ALL,
    Scrollbar,
    Canvas
)


def add_scrollbars(outer, InnerType, *inner_args, **inner_kw):
    """ Creates widget of type `InnerType` inside `outer` widget and adds
vertical and horizontal scroll bars for created widget.
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

    return inner
