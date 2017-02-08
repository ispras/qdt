from Tkinter import \
    Misc

class QDCGUISignalHelper(Misc):

    def qsig_get(self, sig_name):
        qgui = self.winfo_toplevel()
        s = getattr(qgui, "sig_" + sig_name)
        return s

    def qsig_watch(self, sig_name, callback):
        return self.qsig_get(sig_name).watch(callback)

    def qsig_unwatch(self, sig_name, callback):
        return self.qsig_get(sig_name).unwatch(callback)

    def qsig_emit(self, sig_name, *args, **kw):
        return self.qsig_get(sig_name).emit_args(args, kw)
