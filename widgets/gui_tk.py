from .var_widgets import VarTk

from .tk_co_dispatcher import TkCoDispatcher

from common import (
    Notifier,
    SignalDispatcherTask
)

@Notifier("activated", "finished", 'failed', "removed")
class GUITaskManager(TkCoDispatcher):
    def __activate__(self, task):
        TkCoDispatcher.__activate__(self, task)
        self.__notify_activated(task)

    def __finish__(self, task):
        TkCoDispatcher.__finish__(self, task)
        self.__notify_finished(task)

    def __failed__(self, task, exception):
        TkCoDispatcher.__failed__(self, task, exception)
        self.__notify_failed(task)

    def remove(self, task):
        TkCoDispatcher.remove(self, task)
        self.__notify_removed(task)

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
        self.task_manager = GUITaskManager(self, **disp_kw)

        self.signal_dispatcher = SignalDispatcherTask()
        self.task_manager.enqueue(self.signal_dispatcher)

    def mainloop(self, *args, **kw):
        self.task_manager.start_loop()

        VarTk.mainloop(self, *args, **kw)
