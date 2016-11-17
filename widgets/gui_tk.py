from var_widgets import \
    VarTk

from tk_co_dispatcher import \
    TkCoDispatcher

class GUITk(VarTk):

    def __init__(self, **kw):
        # Cut arguments for dispatcher
        disp_kw = {}
        for disp_arg in ("max_tasks", "wait_msec"):
            try:
                disp_kw[disp_arg] = kw.pop(disp_arg)
            except KeyError:
                pass

        VarTk.__init__(self, **kw)
        self.task_manager = TkCoDispatcher(self, **disp_kw)

    def mainloop(self, *args, **kw):
        self.task_manager.start_loop()

        VarTk.mainloop(self, *args, **kw)
