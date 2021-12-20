#!/usr/bin/python

# WARNING! Keep it lightweight. Don't use QDT's `widgets` and so on.

from six.moves.tkinter import (
    Tk,
    Label,
    Entry,
    BOTH,
    StringVar,
    Checkbutton,
    BooleanVar,
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

    root.bind_all("<Return>", lambda *__: root.destroy(), "+")

    showpass_var.trace("w",
        lambda *__: e.config(show = "" if showpass_var.get() else "*")
    )

    showpass_var.set(False)

    e.focus_force()

    root.mainloop()

    return passvar.get()


if __name__ == "__main__":
    from sys import argv
    if len(argv) > 1:
        print(askpass(message = argv[1]))
    else:
        print(askpass())
