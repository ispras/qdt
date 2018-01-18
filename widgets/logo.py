__all__ = [
    "set_logo"
]

from six.moves.tkinter import PhotoImage

from os.path import (
    split,
    join
)
from traceback import print_exc

reported = False

def set_logo(self):

    script_dir, __ = split(__file__)
    if not script_dir:
        script_dir = "."

    logo_file = join(script_dir, "logo.png")

    try:
        # see: https://stackoverflow.com/questions/18537918/set-window-icon
        icon = PhotoImage(file = logo_file)
        self.tk.call("wm", "iconphoto", self._w, icon)
    except:
        if reported:
            return

        print(_("Cannot set window icon").get())
        print_exc()
        reported = True
