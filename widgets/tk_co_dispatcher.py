__all__ = [
    "TkCoDispatcher"
]

from common import CoDispatcher

from time import time

import sys

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
        t0 = time()
        ready = CoDispatcher.iteration(self)
        ti = time() - t0
        if ti > 0.1:

            sys.stderr.write(("Iteration consumed %f sec\n" % ti)
                + "Active tasks:\n  "
                + "\n  ".join(
                    t.generator.__name__ for t in self.active_tasks
                )
                + "\n"
            )
            # Note that, a task may consume so many time just before a call or
            # finish. It will not be presented in the list.

        self.tk.after(1 if ready else self.wait_msec, self.iteration)

    def start_loop(self):
        self.tk.after(0, self.iteration)
