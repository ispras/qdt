from six.moves.tkinter import (
    Tk,
    Canvas,
    Label,
    BOTH,
    Frame
)
from widgets import (
    CanvasFrame
)

if __name__ == "__main__":
    root = Tk()

    root.rowconfigure(0, weight = 1)
    root.columnconfigure(0, weight = 1)

    cnv = Canvas(root, bg = "white")
    cnv.grid(row = 0, column = 0, sticky = "NESW")

    cf = CanvasFrame(cnv, 100, 100)

    cnv.itemconfig(cf.id, width = 150, height = 150)

    Label(cf, text = "Test").pack(fill = BOTH, expand = 0)

    f2 = Frame(cf, bg = "white", width = 100, height = 100)
    f2.pack(fill = BOTH, expand = 1)

    def on_motion(e):
        print (e.x, e.y)

    f2.bind("<Motion>", on_motion, "+")

    root.mainloop()
