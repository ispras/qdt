__all__ = [
    "set_logo"
]

from common import (
    mlget as _,
)
from .pictures import (
    Pictures,
)

from traceback import (
    print_exc,
)


reported = False
logo = Pictures(
    logo = (
        "logo.png",
        # Some versions of Tkinter do not support PNG. Use GIF instead.
        "logo.gif",
    )
)

def set_logo(self):
    try:
        # see: https://stackoverflow.com/questions/18537918/set-window-icon
        self.tk.call("wm", "iconphoto", self._w, logo.logo)
    except:
        global reported

        if reported:
            return

        print(_("Cannot set window icon").get())
        print_exc()
        reported = True
