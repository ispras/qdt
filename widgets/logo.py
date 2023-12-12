__all__ = [
    "set_logo"
]

from common import (
    mlget as _,
)

from os.path import (
    join,
    split,
)
from six.moves.tkinter import (
    PhotoImage,
)
from traceback import (
    print_exc,
)


reported = False

def set_logo(self):

    script_dir, __ = split(__file__)
    if not script_dir:
        script_dir = "."

    png_logo_file = join(script_dir, "logo.png")

    try:
        # see: https://stackoverflow.com/questions/18537918/set-window-icon
        try:
            icon = PhotoImage(file = png_logo_file)
        except:
            # Some versions of Tkinter do not support PNG. Use GIF instead.
            gif_logo_file = join(script_dir, "logo.gif")
            icon = PhotoImage(file = gif_logo_file)

        self.tk.call("wm", "iconphoto", self._w, icon)
    except:
        global reported

        if reported:
            return

        print(_("Cannot set window icon").get())
        print_exc()
        reported = True
