from common import mlget as _

from six.moves.tkinter_tkfiledialog import (
    askdirectory as tk_askdirector,
    askopenfilename,
    asksaveasfilename
)

class CrossDialog(object):
    def __init__(self, master):
        self.master = master

    def ask(self):
        try:
            hk = self.master.winfo_toplevel().hk
        except:
            hk = None
        else:
            hk.disable_hotkeys()

        try:
            return self.__ask__()
        finally:
            if hk:
                hk.enable_hotkeys()

class CrossSaveAsDialog(CrossDialog):
    def __init__(self, master, filetypes = None, title = None):
        super(CrossSaveAsDialog, self).__init__(master)

        self.title = _("Save as") if title is None else title

        self.filetypes = [(_("All files"), '.*')] if filetypes is None \
            else filetypes

    def __ask__(self):
        kw = {
            "title" : self.title.get(),
            "filetypes": [
                (filter_name.get(), filter) for (filter_name, filter) in \
                    self.filetypes
            ]
        }

        return asksaveasfilename(**kw)

def asksaveas(*args, **kw):
    return CrossSaveAsDialog(*args, **kw).ask()

class CrossOpenDialog(CrossDialog):
    def __init__(self, master, filetypes = None, title = None):
        super(CrossOpenDialog, self).__init__(master)

        self.title = _("Open file") if title is None else title

        self.filetypes = [(_("All files"), '.*')] if filetypes is None \
            else filetypes

    def __ask__(self):
        kw = {
            "title" : self.title.get(),
            "filetypes": [
                (filter_name.get(), filter) for (filter_name, filter) in \
                    self.filetypes
            ]
        }

        return askopenfilename(**kw)

def askopen(*args, **kw):
    return CrossOpenDialog(*args, **kw).ask()

class CrossDirectoryDialog(CrossDialog):
    def __init__(self, master, title = None):
        super(CrossDirectoryDialog, self).__init__(master)

        self.title = _("Select directory") if title is None else title

    def __ask__(self):
        kw = {
            "title" : self.title.get()
        }

        return tk_askdirector(**kw)

def askdirectory(*args, **kw):
    return CrossDirectoryDialog(*args, **kw).ask()
