from six.moves.tkinter import (
    Tk,
    RAISED,
    Canvas,
    BOTH,
    HORIZONTAL,
    VERTICAL
)
from widgets import (
    AutoPanedWindow
)


if __name__ == "__main__":
    r = Tk()
    r.title("AutoPanedWindow example")

    a = AutoPanedWindow(r, sashrelief = RAISED, orient = HORIZONTAL)
    a.pack(fill = BOTH, expand = True)

    a.add(Canvas(a, bg = "red"), sticky = "NESW")

    a1 = AutoPanedWindow(a, sashrelief = RAISED, orient = VERTICAL)
    a.add(a1, sticky = "NESW")

    blue = Canvas(a1, bg = "blue")
    a1.add(blue, sticky = "NESW")

    green = Canvas(a1, bg = "green")
    a1.add(green, sticky = "NESW")

    a1.add(Canvas(a1, bg = "brown"), after = blue, sticky = "NESW")

    yellow = Canvas(a, bg = "yellow")
    a.add(yellow, sticky = "NESW")

    a.add(Canvas(a, bg = "pink"), before = yellow, sticky = "NESW")

    r.geometry("800x600")
    r.mainloop()
