__all__ = [
    "ThreadControl"
]

from .gui_frame import (
    GUIFrame
)
from six.moves.tkinter import (
    Label,
    DISABLED,
    NORMAL,
    StringVar
)
from .var_widgets import (
    VarButton,
    VarLabel
)
from common import (
    mlget as _
)

from os.path import (
    split,
    join
)
from sys import (
    path as python_path
)
from time import (
    time
)
from threading import (
    Thread,
    Event
)

for mod in ("pyrsp",):
    path = join(split(split(__file__)[0])[0], mod)
    if path not in python_path:
        python_path.insert(0, path)

from pyrsp.utils import (
    rsp_decode
)

# prevents blokning thread state during fast stop-resume
BLINK_THRESHOLD = 0.100 # sec

STOP_REASONS = (
    "watch", "rwatch", "awatch", "library", "replaylog", "swbreak", "hwbreak",
    "fork", "vfork", "vforkdone", "exec", "create"
)
REASON_UNKNOWN = "[stopped]"
REASON_BLINKING = "[blink]"


class UpdaterThread(Thread):
    """ Updates widgets those display inferior thread states. It avoids fast
    widget updation by marking it as "blinking".
    """

    def __init__(self, widget, *a, **kw):
        self._debug = kw.pop("debug", False)
        super(UpdaterThread, self).__init__(*a, **kw)
        self._wgt = widget
        self.cancel = Event()

    def run(self):
        wgt = self._wgt
        d = self._debug

        if d:
            print("%s is started for %s" % (type(self).__name__, wgt))

        wait = self.cancel.wait
        threads = wgt.threads

        while not wait(BLINK_THRESHOLD):
            cur = time()
            for t in threads.values():
                if cur - t.last_reason_update > BLINK_THRESHOLD:
                    t.blink = False
                    t.reason.set(t.last_reason)
                elif t.blink:
                    t.reason.set(REASON_BLINKING)
                else:
                    t.blink = True

        if d:
            print("%s for %s is exiting" % (type(self).__name__, wgt))


class InferiorThread(object):

    def __init__(self, tid):
        self.tid = tid

        self.reason = StringVar()
        self.last_reason_update = time()
        self.last_reason = REASON_UNKNOWN
        self.blink = False

    def update_reason(self, reason):
        self.last_reason = reason
        self.last_reason_update = time()


COLUMN_NAME = 0
COLUMN_STATE = 1
COLUMN_STOP = 2
COLUMN_RESUME = 3
COLUMNS = 4


class ThreadControl(GUIFrame):

    def __init__(self, master, **kw):
        GUIFrame.__init__(self, master, **kw)

        """
 Thread   | stop reason |  Stop    | Resume
----------+-------------+----------+--------
Thread ID |     ...     |      Controls ...
----------+-------------+---
   ...    |   ...
        """

        self.columnconfigure(COLUMN_NAME, weight = 1)
        self.columnconfigure(COLUMN_STATE, weight = 0)
        self.columnconfigure(COLUMN_STOP, weight = 0)
        self.columnconfigure(COLUMN_RESUME, weight = 0)

        self.__next_row = 0

        title_row = self.__get_row()
        lb_title = VarLabel(self, text = _("Thread Control"))
        lb_title.grid(
            row = title_row,
            column = COLUMN_NAME,
            columnspan = COLUMNS,
            sticky = "NESW"
        )

        tid_row = self.__get_row()

        lb_thread = VarLabel(self, text = _("Thread"))
        lb_thread.grid(row = tid_row, column = COLUMN_NAME, sticky = "NESW")

        lb_state = VarLabel(self, text = _("State"))
        lb_state.grid(row = tid_row, column = COLUMN_STATE, sticky = "NESW")

        self.bt_stop_all = bt = VarButton(self,
            text = _("Stop"),
            command = self._on_stop_all,
            state = DISABLED
        )
        """ TODO: extra API required
        bt.grid(row = tid_row, column = COLUMN_STOP, sticky = "NESW")
        """

        self.bt_resume_all = bt = VarButton(self,
            text = _("Resume"),
            command = self._on_resume_all,
            state = DISABLED
        )
        """ TODO: extra API required
        bt.grid(
            row = tid_row,
            column = COLUMN_RESUME,
            sticky = "NESW"
        )
        """

        self.runtime = None

    def _on_resume_all(self):
        pass # self.target.resume_thread()

    def _on_stop_all(self):
        pass # self.target.stop_thread()

    def __get_row(self):
        r = self.__next_row
        self.__next_row = r + 1
        self.rowconfigure(r, weight = 0)
        return r

    def set_runtime(self, runtime):
        if self.runtime is not None:
            raise NotImplementedError("May not swap runtime")

        self.bt_stop_all.config(state = NORMAL)
        self.bt_resume_all.config(state = NORMAL)

        self.runtime = runtime

        self.threads = {}

        runtime.watch_stop(self._on_stop)
        runtime.watch_resume(self._on_resume)

        for tid in runtime.target.get_thread_info()[2]:
            self._account_thread(tid)

        self._updater = _updater = UpdaterThread(self)
        _updater.start()
        self.bind("<Destroy>", lambda _: _updater.cancel.set())

    def _account_thread(self, tid):
        t = InferiorThread(tid)
        self.threads[tid] = t

        thread_row = self.__get_row()

        lb_id = Label(self, text = tid)
        lb_id.grid(row = thread_row, column = COLUMN_NAME, sticky = "NESW")

        lb_reason = VarLabel(self, textvar = t.reason)
        lb_reason.grid(
            row = thread_row,
            column = COLUMN_STATE,
            sticky = "NESW"
        )

        return t

    def _provide_thread(self, tid):
        try:
            t = self.threads[tid]
        except KeyError:
            t = self._account_thread(tid)
        return t

    def _on_stop(self, kind, sig, event):
        if kind == 'T':
            try:
                raw_tid = event["thread"]
            except KeyError:
                print("Stop event without a thread ID: %s%02x%s" % (
                    kind, sig,
                    ";".join((str(k) + ':' + str(v)) for k, v in event.items())
                ))
                return

            for reason in STOP_REASONS:
                if reason in event:
                    break
            else:
                reason = REASON_UNKNOWN

            tid = rsp_decode(raw_tid)
            t = self._provide_thread(tid)
            t.update_reason(reason)
        else:
            print("Unknown stop event kind " + kind)

    def _on_resume(self, tid):
        if tid[-2:] == "-1":
            for t in self.threads.values():
                t.update_reason("resumed")
        else:
            t = self._provide_thread(tid)
            t.update_reason("resumed")
