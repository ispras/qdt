#!/usr/bin/env python

# If interpreter is absent `sudo` prints "no such file" on `askpass.py`
# while "no such file" should be printed on `python`.
# Using `/usr/bin/env` makes error message accurate because `env`
# correctly prints "no such file" on `python`.

# WARNING! Keep it lightweight. Don't use QDT's `widgets` and so on.

from six.moves.tkinter import (
    BooleanVar,
    BOTH,
    Checkbutton,
    Entry,
    Label,
    StringVar,
    Tk,
)


def askpass(
    title = "Enter password",
    message = "Superuser rights are required. Input then press 'Enter'",
):
    root = Tk()
    root.title(title)
    Label(root,
        text = message,
    ).pack(
        fill = BOTH,
        expand = True,
    )

    showpass_var = BooleanVar(root)
    Checkbutton(root,
        text = "Show password",
        variable = showpass_var,
    ).pack(
        fill = BOTH,
        expand = True,
    )

    passvar = StringVar(root)
    e = Entry(root,
        textvar = passvar,
    )
    e.pack(
        fill = BOTH,
        expand = True,
    )

    root._entered = False

    def on_return(*__):
        root._entered = True
        root.destroy()

    e.bind_all("<Return>", on_return, "+")
    e.bind_all("<Escape>", lambda *__: root.destroy(), "+")

    showpass_var.trace("w",
        lambda *__: e.config(show = "" if showpass_var.get() else "*")
    )

    showpass_var.set(False)

    e.focus_force()

    root.mainloop()

    if root._entered:
        return passvar.get()


if __name__ == "__main__":
    from sys import argv
    if len(argv) > 1:
        res = askpass(message = argv[1])
    else:
        res = askpass()
    if res is not None:
        print(res)
