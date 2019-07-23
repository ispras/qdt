# Some playing with Tkinter events

from six.moves.tkinter import (
    Tk,
    Frame,
    Label,
    BOTH,
    Text,
    END,
    Scrollbar,
    TOP,
    RIGHT,
    Button,
    LEFT
)
from six.moves.tkinter_ttk import (
    Combobox
)


def main():
    root = Tk()

    Label(root,
        text = "Outer label"
    ).pack(
        fill = BOTH,
        expand = True,
        side = TOP
    )

    frame = Frame(root)
    frame.pack(fill = BOTH, expand = True, side = TOP)

    sb = Scrollbar(frame)
    sb.pack(fill = BOTH, side = RIGHT)

    if False:
        def event_break(e):
            print("breaking %r" % e)
            return "break"

        frame.bind_all("<Button-4>", event_break, "+")

    lb = Label(frame, text = "Label")
    lb.pack(fill = BOTH, side = TOP)

    cb = Combobox(frame, values = ("1", "2", "3"))
    cb.pack(fill = BOTH, side = TOP)

    text = Text(frame)
    text.pack(fill = BOTH, expand = True, side = TOP)
    text.insert(END, "A\nMultiline\nMessage")

    bt1 = Button(frame, text = "Bt#1")
    bt1.pack(side = LEFT)

    bt2 = Button(frame, text = "Bt#2")
    bt2.pack(side = RIGHT)


    if False:
        def event(e):
            print("event %r" % e)

        frame.bind("<Button-4>", event, "+")

    scrollable = set(["TCombobox", "Scrollbar", "Text"])

    def event_all(e):
        w = e.widget

        m = e.widget
        while m is not None:
            if m is frame:
                break
            m = m.master
        else:
            print("Outer widget")
            return

        cls = w.winfo_class()
        print("cls = " + cls)
        if cls in scrollable:
            return
        # scroll here

    frame.bind_all("<Button-4>", event_all, "+")

    root.mainloop()


if __name__ == "__main__":
    exit(main())
