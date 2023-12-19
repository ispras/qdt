__all__ = [
    "CoStatusView"
]

from common import (
    FormatVar,
)
from .gui_tk import (
    GUITk,
)
from .statusbar import (
    Statusbar,
)

from six.moves import (
    zip,
)
from six.moves.tkinter import (
    IntVar,
)


# Note: `object` is required for `property` decorator
class CoStatusView(Statusbar, object):
    """ Shows amounts of scheduled, waiting (for other coroutine), active and
finished coroutines.
    """

    def __init__(self, *a, **kw):
        color_tasks = kw.pop("color_tasks", "red")
        color_callers = kw.pop("color_callers", "orange")
        color_active = kw.pop("color_active", None)
        color_finished = kw.pop("color_finished", "grey")

        Statusbar.__init__(self, *a, **kw)

        # task_manager property backed value
        self._tm = None

        # create widgets
        for group, c in zip(
            TASK_GROUPS,
            (color_tasks, color_callers, color_active, color_finished)
        ):
            v = IntVar(self)
            setattr(self, "_var_" + group, v)

            lb = self.right(FormatVar(value = "%u") % v)
            if c is not None:
                lb.config(fg = c)

        # auto bind to task manager
        guitk = self.winfo_toplevel()
        if isinstance(guitk, GUITk):
            self.task_manager = guitk.task_manager

        self.bind("<Destroy>", self._on_destroy, "+")

    @property
    def task_manager(self):
        return self._tm

    @task_manager.setter
    def task_manager(self, tm):
        prev_tm = self._tm
        if prev_tm is tm:
            return
        self._tm = tm

        handler = self._task_state_changed
        for e in tm._events:
            if prev_tm is not None:
                prev_tm.unwatch(e, handler)
            tm.watch(e, handler)

    def _task_state_changed(self, __):
        for group in TASK_GROUPS:
            var = getattr(self, "_var_" + group)
            cur_val = len(getattr(self.task_manager, group))
            if cur_val != var.get():
                var.set(cur_val)

    def _on_destroy(self, __):
        tm = self._tm
        if tm is not None:
            handler = self._task_state_changed
            for e in tm._events:
                tm.unwatch(e, handler)

TASK_GROUPS = ("tasks", "callers", "active_tasks", "finished_tasks")
