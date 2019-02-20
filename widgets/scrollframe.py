__all__ = [
    "add_scrollbar"
]


from six.moves.tkinter import (
    ALL,
    Scrollbar,
    Canvas
)


def add_scrollbar(outer, InnerType, *inner_args, **inner_kw):
    """ Creates widget of type `InnerType` inside `outer` widget and adds
vertical scroll bar for created widget.
    """

    outer.rowconfigure(0, weight = 1)
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

    scrollbar = Scrollbar(outer,
        orient = "vertical",
        command = canvas.yview
    )
    scrollbar._visible = False

    canvas.configure(yscrollcommand = scrollbar.set)

    def scrollbar_visibility():
        "Automatically shows & hides the scroll bar."

        cnv_h = canvas.winfo_height()
        inner_h = inner.winfo_height()

        if inner_h <= cnv_h:
            if scrollbar._visible:
                scrollbar.grid_forget()
                scrollbar._visible = False
        elif inner_h > cnv_h:
            if not scrollbar._visible:
                scrollbar.grid(row = 0, column = 1, sticky = "NESW")
                scrollbar._visible = True

    def inner_configure(_):
        cnf = dict(
            scrollregion = canvas.bbox(ALL)
        )
        cnv_h = canvas.winfo_height()
        inner_h = inner.winfo_height()

        if inner_h < cnv_h:
            cnf["height"] = inner_h
            # `scrollbar_visibility` will be called during the canvas
            # resizing by `canvas_configure`
        else:
            scrollbar_visibility()

        canvas.configure(**cnf)

    inner.bind("<Configure>", inner_configure, "+")

    def canvas_configure(_):
        scrollbar_visibility()
        canvas.itemconfig(inner_id, width = canvas.winfo_width())

    canvas.bind("<Configure>", canvas_configure, "+")

    return inner
