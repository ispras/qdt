#!/usr/bin/python

from six.moves.tkinter import (
    X,
    Label,
    CURRENT,
    PhotoImage,
    BOTH,
    Tk,
    Canvas
)
from os import (
    name as os_name
)
from os.path import (
    dirname,
    join
)
from PIL import (
    Image,
    ImageTk
)
from widgets import (
    KeyboardSettings
)

# Use 63 DPI to get keyboard.png from keyboard.svg
# Ex.:
# inkscape --without-gui --export-dpi=63 keyboard.svg --export-png=keyboard.png

KBD_IMG = join(dirname(__file__), "keyboard.png")

if __name__ == "__main__":
    root = Tk()
    root.title("Keyboard")

    cnv = Canvas(root, bg = "white")
    cnv.pack(fill = BOTH, expand = True)

    image = Image.open(KBD_IMG)
    imagetk = ImageTk.PhotoImage(image)

    cnv.create_image(image.size[0] >> 1, image.size[1] >> 1, image = imagetk)
    cnv.configure(width = image.size[0], height = image.size[1])

    lb_code = Label(root)
    lb_code.pack(fill = X, expand = False)

    def resize():
        # XXX: it's a bit less that ideally needed because of borders
        w, h = image.size
        h += lb_code.winfo_reqheight()
        root.geometry("%ux%u" % (w, h))

    root.after(10, resize)

    def shift_key_positions(kbd, dx, dy):
        for i, p in enumerate(kbd.points):
            kbd.points[i] = p[0] + dx, p[1] + dy

    with KeyboardSettings(points = [], os_codes = {}) as kbd:
        button_index = None

        kbd._codes = kbd.os_codes.setdefault(os_name, {})

        # shift_key_positions(-25, -30)

        MSG_SET = ("Press LMB again to remove the point, "
            "keyboard to change or RMB to reset selection. Current: "
        )

        def update(message = "Press LMB to add/select button or keyboard"
            " key to highlight it on the scheme."
        ):
            global button_index

            if button_index is None:
                lb_code.configure(text = message)
            else:
                code_data = kbd._codes.get(button_index, None)
                if code_data is None:
                    lb_code.configure(text = "Press keyboard to set or LMB "
                        "again no remove the point..."
                    )
                else:
                    lb_code.configure(text = message + "%s %s" % code_data)

        def draw_point(x, y, fill = "red"):
            cnv.create_oval(x - 5, y - 5, x + 5, y + 5, fill = fill)

        for x, y in kbd.points:
            draw_point(x, y)

        def unselect():
            global button_index

            if button_index is None:
                return

            cnv.itemconfig(cnv.find_closest(*kbd.points[button_index]),
                fill = "red"
            )

        def on_click_1(e):
            global button_index

            unpress()

            for i, (x, y) in enumerate(kbd.points):
                if (x - e.x) ** 2 + (y - e.y) ** 2 <= 25:
                    break
            else:
                unselect()
                button_index = len(kbd.points)
                kbd.points.append((e.x, e.y))
                draw_point(e.x, e.y, fill = "green")
                update()
                return

            if i == button_index: # remove on second click
                unselect()
                button_index = None
                del kbd.points[i]
                kbd._codes.pop(i, None) # ignore absence
                cnv.delete(CURRENT)
                update()
            else:
                unselect()
                button_index = i
                cnv.itemconfig(CURRENT, fill = "green")
                update(message = MSG_SET)

        cnv.bind("<Button-1>", on_click_1, "+")

        def on_click_3(_):
            global button_index

            if button_index is not None:
                unselect()
                button_index = None
                update()

        cnv.bind("<Button-3>", on_click_3, "+")

        pressed = []

        def unpress():
            if pressed:
                for iid in pressed:
                    cnv.itemconfig(iid, fill = "red")

                del pressed[:]

        def on_key(e):
            global button_index
            global pressed

            if button_index is None:
                unpress()
                update(message = "pressed: %s, %s" % (e.keycode, e.keysym))

                for i, code_data in kbd._codes.items():
                    if code_data is None:
                        continue
                    if code_data[0] != e.keycode:
                        continue
                    iid = cnv.find_closest(*kbd.points[i])
                    cnv.itemconfig(iid, fill = "orange")
                    pressed.append(iid)

                return

            kbd._codes[button_index] = (e.keycode, e.keysym)
            update(message = MSG_SET)

        root.bind_all("<Key>", on_key, "+")

        update()

        root.mainloop()
