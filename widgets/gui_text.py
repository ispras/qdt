__all__ = [
    "GUIText"
  , "READONLY"
  , "generate_modified"
  , "generates_modified"
]

# based on http://tkinter.unpythonic.net/wiki/ReadOnlyText

from six.moves.tkinter import (
    Text,
    NORMAL
)
from common import (
    notifier
)

READONLY = "readonly"

from sys import (
    version_info
)
try:
    if version_info[0] < 3 or version_info[0] == 3 and version_info[1] <= 5:
        from idlelib.WidgetRedirector import (
            WidgetRedirector
        )
    else:
        from idlelib.redirector import (
            WidgetRedirector
        )
except ImportError as e:
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
    def __init__(self, master, **kw):
        read_only = False
        try:
            state = kw["state"]
        except:
            pass
        else:
            if state == READONLY:
                read_only = True
                kw["state"] = NORMAL

        Text.__init__(self, master, **kw)

        self.redirector = WidgetRedirector(self)

        if read_only:
            self.__read_only = True
            """ Note that software editing is still possible by calling those
            "insert" and "delete". """
            self.insert = self.redirector.register("insert", _break)
            self.delete = self.redirector.register("delete", _break)


# Based on: https://stackoverflow.com/questions/40617515/python-tkinter-text-modified-callback

TEXT_CHANGERS = set(["insert", "delete", "replace"])

def generate_modified(text):
    "Adds report on commands changing Text widget"
    tk, w = text.tk, text._w

    orig = w + "_orig"

    def proxy(command, *args):
        cmd = (orig, command) + args
        result = tk.call(cmd)

        if command in TEXT_CHANGERS:
            text.event_generate("<<TextModified>>")

        return result

    tk.call("rename", w, orig)
    tk.createcommand(w, proxy)

def generates_modified(TextClass):
    """ A `notifier` issuing "modified" event on commands changing Text
widget. An event handler is also given the Tcl command with arguments.
    """

    def __init__(self, *a, **kw):
        TextClass.__init__(self, *a, **kw)

        tk, w = self.tk, self._w

        self.__orig = orig = w + "_original"

        tk.call("rename", w, orig)
        tk.createcommand(w, self._proxy)

    def _proxy(self, command, *args):
        cmd = (self.__orig, command) + args
        result = self.tk.call(cmd)

        if command in TEXT_CHANGERS:
            # XXX: I don't know why, but `self.__notify_modified` raises an
            # attribute error there
            self._GUITextM__notify_modified(command, *args)

        return result

    return notifier("modified")(type(TextClass.__name__ + "M", (TextClass,), {
        "__init__" : __init__,
        "_proxy" : _proxy
    }))
