__all__ = [
    "GUIText"
  , "READONLY"
]

# based on http://tkinter.unpythonic.net/wiki/ReadOnlyText

from six.moves.tkinter import (
    Text,
    NORMAL
)

READONLY = "readonly"

try:
    from idlelib.WidgetRedirector import WidgetRedirector
except ImportError as e:
    from sys import version_info

    raise ImportError("Cannot import from idlelib. Try:"
        " sudo apt-get install idle-python%d.%d" % version_info[:2]
    )

def _break(*args, **kw):
    return "break"

class GUIText(Text):
    """
    TODO:
    * READONLY state support for config, configure, _configure e.t.c.
    * returning READONLY by config, configure, _configure e.t.c.
    * switching back to NORMAL, DISABLED
    """
    def __init__(self, **kw):
        read_only = False
        try:
            state = kw["state"]
        except:
            pass
        else:
            if state == READONLY:
                read_only = True
                kw["state"] = NORMAL

        Text.__init__(self, **kw)

        self.redirector = WidgetRedirector(self)

        if read_only:
            self.__read_only = True
            """ Note that software editing is still possible by calling those
            "insert" and "delete". """
            self.insert = self.redirector.register("insert", _break)
            self.delete = self.redirector.register("delete", _break)
