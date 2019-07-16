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


class ScrollbarConfigure(object):

    def __init__(self, outer, InnerType, *inner_args, **inner_kw):
        self.scrolltag = "tag_" + str(next(self._ids))
        outer.rowconfigure(0, weight = 1)
        outer.rowconfigure(1, weight = 0)
        outer.columnconfigure(0, weight = 1)
        outer.columnconfigure(1, weight = 0)

        # container for inner frame, it supports scrolling
        self.canvas = canvas =  Canvas(outer, width = 1, height = 1)
        self.canvas.grid(row = 0, column = 0, sticky = "NESW")

        self.inner = inner = InnerType(canvas, *inner_args, **inner_kw)

        self.inner_id = self.canvas.create_window((0, 0),
            window = self.inner,
            anchor = "nw"
        )

        self.h_sb = Scrollbar(outer,
            orient = "horizontal",
            command = canvas.xview
        )
        self.h_sb._visible = False

        self.v_sb = Scrollbar(outer,
            orient = "vertical",
            command = canvas.yview
        )
        self.v_sb._visible = False

        canvas.configure(
            xscrollcommand = self.h_sb.set,
            yscrollcommand = self.v_sb.set
        )

        inner.bind("<Configure>", self.inner_configure, "+")
        canvas.bind("<Configure>", self.canvas_configure, "+")

    def scrollbar_visibility(self):
        "Automatically shows & hides the scroll bar."

        cnv_w, cnv_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        inner_w, inner_h = self.inner.winfo_width(), self.inner.winfo_height()

        if inner_w <= cnv_w:
            if self.h_sb._visible:
                self.h_sb.grid_forget()
                self.h_sb._visible = False
        else:
            if not self.h_sb._visible:
                self.h_sb.grid(row = 1, column = 0, sticky = "NESW")
                self.h_sb._visible = True

        if inner_h <= cnv_h:
            if self.v_sb._visible:
                self.v_sb.grid_forget()
                self.v_sb._visible = False
        else:
            if not self.v_sb._visible:
                self.v_sb.grid(row = 0, column = 1, sticky = "NESW")
                self.v_sb._visible = True

    def inner_configure(self, _):
        self.scrollbar_visibility()
        self.canvas.configure(
            scrollregion = self.canvas.bbox(ALL),
            # Require as many space as inner widget do.
            width = self.inner.winfo_reqwidth(),
            height = self.inner.winfo_reqheight()
        )

    def canvas_configure(self, e):
        self.scrollbar_visibility()
        # Get to the inner widget at least desired space.
        # Stretch it when possible.

        self.canvas.itemconfig(self.inner_id,
            width = max(e.width, self.inner.winfo_reqwidth()),
            height = max(e.height, self.inner.winfo_reqheight())
        )


def add_scrollbars(outer, InnerType, *inner_args, **inner_kw):
    """ Creates widget of type `InnerType` inside `outer` widget and adds
vertical and horizontal scroll bars for created widget.
    """

    mws = ScrollbarConfigure(outer, InnerType, *inner_args, **inner_kw)

    return mws.inner
