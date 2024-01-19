#!/usr/bin/python

from six.moves.tkinter import (
    X,
    Label,
    BOTH,
    Tk,
    Canvas
)
from os import (
    name as os_name
)
from widgets import (
    KeyboardSettings
)
from common import (
    bidict
)
from six.moves import (
    zip,
)


inner_pad = 4
outer_pad = 10
default_w = 40
default_h = 40
key_lb_fmt = "[%s]\n%.5s" # % (code, symbol)
color_set = "white"
color_selected = "green"
color_not_set = "grey"
color_pressed = "orange"


class PlaceHolder(object):

    def __init__(self, w = 0, h = default_h):
        # w = 0 - minimal width of PlaceHolder
        self.x = None
        self.y = None
        self.w = w
        self.h = h
        self.expandable = False


class RowHolder(PlaceHolder):

    def __init__(self, h = default_h):
        super(RowHolder, self).__init__(h = h)
        self.expandable = True


RH = RowHolder


class ButtonHolder(PlaceHolder):

    def __init__(self):
        super(ButtonHolder, self).__init__(w = default_w, h = default_h)


BH = ButtonHolder


class Separator(PlaceHolder):

    def __init__(self):
        super(Separator, self).__init__()
        self.expandable = True


S = Separator


class GroupSeparator(PlaceHolder):

    def __init__(self):
        super(GroupSeparator, self).__init__(w = 30)


GS = GroupSeparator


class Button(PlaceHolder):

    def __init__(self, w = default_w, h = default_h):
        super(Button, self).__init__(w = w, h = h)


B = Button


class LShift(Button):

    def __init__(self):
        super(LShift, self).__init__(w = 50)


Super = LShift


Alt = LShift


Menu = LShift


class Tab(Button):

    def __init__(self):
        super(Tab, self).__init__(w = 60)


Ctrl = Tab


class Caps(Button):

    def __init__(self):
        super(Caps, self).__init__(w = 70)


class TwoRowButton(Button):

    def __init__(self):
        super(TwoRowButton, self).__init__(h = 2 * default_h + inner_pad)


Plus = TwoRowButton


REnter = TwoRowButton


class TwoColumnButton(Button):

    def __init__(self):
        super(TwoColumnButton, self).__init__(w = 2 * default_w + inner_pad)


Zero = TwoColumnButton


class ExpandableButton(Button):

    def __init__(self):
        super(ExpandableButton, self).__init__(w = 0)
        self.expandable = True


LEnter = ExpandableButton


RShift = ExpandableButton


Space = ExpandableButton


BackSlash = ExpandableButton


def prepare_group(group, global_offset_w):
    rows_w = list(map(
        lambda row : sum(b.w for b in row) + inner_pad * max(len(row) - 1, 0),
        group
    ))
    max_w = max(rows_w)

    for w, row in zip(rows_w, group):
        if w == max_w:
            continue
        expandable = list(filter(lambda x: x.expandable, row))
        count = len(expandable)
        if count == 0:
            raise ValueError(
                "Wrong layout: no expanding elements in a short row"
            )
        w1, w2 = divmod(max_w - w, count)
        for i, item in enumerate(expandable):
            item.w = w1 + int(i < w2)

    offset_h = outer_pad
    for row in group:
        offset_w = global_offset_w
        for item in row:
            item.x = offset_w
            item.y = offset_h
            offset_w += item.w + inner_pad
        offset_h += min(item.h for item in row) + inner_pad

    return max_w

def rB(count):
    return [B() for __ in range(count)]

def generate_buttons():
    # See:
    # https://support.microsoft.com/en-us/help/17073/windows-using-keyboard

    # Use UK and US keyboard layout at the same time
    # See: https://en.wikipedia.org/wiki/British_and_American_keyboards

    layout = [
        [B(), S()] + rB(4) + [S()] + rB(4) + [S()] + rB(4) + [GS()] + rB(3) +
            [GS(), RH()],
        [RH(h = 10), GS(), RH(h = 10), GS(), RH(h = 10)],
        rB(15) + [GS()] + rB(3) + [GS()] + rB(4),
        [Tab()] + rB(12) + [BackSlash(), GS()] + rB(3) + [GS()] + rB(3) +
            [Plus()],
        [Caps()] + rB(12) + [LEnter(), GS(), RH(), GS()] + rB(3) + [BH()],
        [LShift()] + rB(11) + [RShift(), GS()] + rB(3) + [GS()] + rB(3) +
            [REnter()],
        [Ctrl(), Super(), Alt(), Space(), Alt(), Super(), Menu(), Ctrl()] +
            [GS()] + rB(3) + [GS(), Zero(), B(), BH()]
    ]

    row = 0
    all_buttons = []
    for line in layout:
        only_buttons = list(filter(lambda x: isinstance(x, Button), line))
        for column, button in enumerate(only_buttons):
            button.pos = (float(row), float(column))
        if only_buttons:
            all_buttons.extend(only_buttons)
            row += 1

    groups = []
    for row in layout:
        new_row = []
        sub_row = []
        for item in row:
            sub_row.append(item)
            if isinstance(item, GS):
                new_row.append(sub_row)
                sub_row = []
        else:
            if sub_row:
                new_row.append(sub_row)
        groups.append(new_row)

    if len(set(len(row) for row in groups)) > 1:
        raise ValueError("Wrong layout: different number of groups in rows")

    offset_w = outer_pad
    for group in zip(*groups):
        offset_w += prepare_group(group, offset_w)

    w = offset_w + outer_pad
    h = max(b.h + b.y for b in all_buttons) + outer_pad
    return all_buttons, w, h

if __name__ == "__main__":
    root = Tk()
    root.title("Keyboard")

    cnv = Canvas(root, bg = "white")
    cnv.pack(fill = BOTH, expand = True)

    buttons, w, h = generate_buttons()

    cnv.configure(width = w, height = h)

    lb_code = Label(root)
    lb_code.pack(fill = X, expand = False)

    def resize():
        # XXX: it's a bit less that ideally needed because of borders
        root.geometry("%ux%u" % (w, h + lb_code.winfo_reqheight()))

    root.after(10, resize)

    id2b = bidict()
    b2id = id2b.mirror
    b2tid = {} # button index (position) to text item id

    for b in buttons:
        iid = cnv.create_rectangle(b.x, b.y, b.x + b.w, b.y + b.h,
            fill = color_not_set # non transparent rectangles
        )
        id2b[iid] = b.pos

        b2tid[b.pos] = cnv.create_text(b.x + (b.w >> 1), b.y + (b.h >> 1),
            justify = "center"
        )

    with KeyboardSettings(os_codes = {}) as kbd:
        button_index = None

        kbd._codes = kbd.os_codes.setdefault(os_name, {})

        MSG_SET = ("Press LMB to select other button or clear current button,"
            " keyboard key to change or RMB to reset selection. Current: "
        )

        def update(message = "Press LMB to select button or keyboard"
            " key to highlight it on the scheme."
        ):
            global button_index

            if button_index is None:
                lb_code.configure(text = message)
            else:
                code_data = kbd._codes.get(button_index, None)
                if code_data is None:
                    lb_code.configure(text = "Press keyboard key to set, LMB"
                        " to select button or RMB to reset selection."
                    )
                else:
                    lb_code.configure(text = message + "%s %s" % code_data)

        for b_index, key in kbd._codes.items():
            cnv.itemconfig(b2id[b_index], fill = color_set)
            cnv.itemconfig(b2tid[b_index], text = key_lb_fmt % key)

        def unselect():
            global button_index

            if button_index is None:
                return

            if kbd._codes.get(button_index, None):
                color = color_set
            else:
                color = color_not_set

            cnv.itemconfig(b2id[button_index], fill = color)

        def on_click_1(e):
            global button_index

            unpress()

            iids = cnv.find_overlapping(e.x, e.y, e.x, e.y)

            if not iids:
                return

            iid = iids[0]
            b_index = id2b[iid]

            if kbd._codes.get(b_index, None) is None:
                unselect()
                button_index = b_index
                cnv.itemconfig(iid, fill = color_selected)
                update()
                return

            if b_index == button_index: # remove on second click
                unselect()
                button_index = None
                kbd._codes.pop(b_index, None) # ignore absence
                cnv.itemconfig(iid, fill = color_not_set)
                cnv.itemconfig(b2tid[b_index], text = "")
                update()
            else:
                unselect()
                button_index = b_index
                cnv.itemconfig(iid, fill = color_selected)
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
                    cnv.itemconfig(iid, fill = color_set)

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
                    iid = b2id[i]
                    cnv.itemconfig(iid, fill = color_pressed)
                    pressed.append(iid)

                return

            key = (e.keycode, e.keysym)

            kbd._codes[button_index] = key

            cnv.itemconfig(b2tid[button_index],
                text = key_lb_fmt % key
            )
            update(message = MSG_SET)

        root.bind_all("<Key>", on_key, "+")

        update()

        root.mainloop()
