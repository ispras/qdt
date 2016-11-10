from common import \
    CoDispatcher

class TkCoDispatcher(CoDispatcher):
    """
    The coroutine task dispatcher uses Tk.after method to spread task work
peaces among Tkinter event driven GUI model.
    """
    def __init__(self, tk, wait_msec = 500, **kw):
        disp_tk = {}
        for disp_arg in ("max_tasks"):
            try:
                disp_tk[disp_arg] = kw.pop(disp_arg)
            except KeyError:
                pass
        CoDispatcher.__init__(self, **disp_tk)

        self.wait_msec = wait_msec
        self.tk = tk

    def iteration(self):
        ready = CoDispatcher.iteration(self)

        self.tk.after(1 if ready else self.wait_msec, self.iteration)

    def start_loop(self):
        self.tk.after(0, self.iteration)
