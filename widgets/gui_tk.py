__all__ = [
    "GUITaskManager"
  , "GUITk"
]

from common import (
    lazy,
    notifier,
    SignalDispatcherTask,
)
from .gui_error import (
    TaskErrorDialog,
)
from .hotkey import (
    HotKey,
)
from .logo import (
    set_logo,
)
from .tk_co_dispatcher import (
    TkCoDispatcher,
)
from .tk_geometry_helper import (
    TkGeometryHelper,
)
from .var_widgets import (
    VarTk,
)


@notifier("activated", "finished", "failed", "removed")
class GUITaskManager(TkCoDispatcher):

    def _activate(self, task):
        TkCoDispatcher._activate(self, task)
        self.__notify_activated(task)

    def _finish(self, task, ret):
        TkCoDispatcher._finish(self, task, ret)
        self.__notify_finished(task)

    def _failed_(self, task, exception):
        TkCoDispatcher._failed(self, task, exception)
        self.__notify_failed(task)

    def __root_task_failed__(self, task):
        TaskErrorDialog(task)

    def remove(self, task):
        TkCoDispatcher.remove(self, task)
        self.__notify_removed(task)


class GUITk(VarTk, TkGeometryHelper):

    def __init__(self, **kw):
        # Cut arguments for dispatcher
        disp_kw = {}
        for disp_arg in ("max_tasks", "wait_msec"):
            try:
                disp_kw[disp_arg] = kw.pop(disp_arg)
            except KeyError:
                pass

        VarTk.__init__(self, **kw)

        set_logo(self)

        self.task_manager = GUITaskManager(self, **disp_kw)

        self.signal_dispatcher = SignalDispatcherTask()
        self.task_manager.enqueue(self.signal_dispatcher)

    @lazy
    def hk(self):
        return HotKey(self)

    def mainloop(self, *args, **kw):
        self.task_manager.start_loop()

        VarTk.mainloop(self, *args, **kw)

    def enqueue(self, co_task):
        self.task_manager.enqueue(co_task)

    def cancel_task(self, co_task):
        self.task_manager.remove(co_task)

    def destroy(self):
        self.last_geometry = self.get_geometry()
        VarTk.destroy(self)
