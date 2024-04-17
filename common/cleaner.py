__all__ = [
    "Cleaner"
  , "get_cleaner"
]

from .os_wrappers import (
    demonize,
)

from multiprocessing import (
    JoinableQueue,
    Process
)
from os import (
    getpid
)
from os.path import (
    exists
)
from psutil import (
    pid_exists
)
from shutil import (
    rmtree
)
from traceback import (
    print_exc
)
from six.moves.queue import (
    Empty
)
from os import (
    name as os_name
)
from six import (
    PY2,
)


class Cleaner(Process):
    """ Watches for a process and does scheduled actions after it terminated.
The main purpose is to clean environment up after failed process because of
it cannot do it by self.
    """

    def __init__(self,
        watch_pid = None,
        poll_period = 1.,
        name = None
    ):
        super(Cleaner, self).__init__(name = name)

        if watch_pid is None:
            watch_pid = getpid()
        self.watch_pid = watch_pid

        self.poll_period = poll_period
        self._task_queue = JoinableQueue()
        self._clean_tasks = []
        self._next_id = 0

    def run(self):
        demonize()

        while pid_exists(self.watch_pid):
            self._read_tasks()

        self._read_tasks(False)

        for t, a, kw, __ in self._clean_tasks:
            try:
                t(*a, **kw)
            except:
                # A failure of a callback must not affect other
                print_exc()

    def _read_tasks(self, wait = True):
        q = self._task_queue
        while True:
            try:
                msg = q.get(wait, self.poll_period)
            except Empty:
                break
            else:
                if isinstance(msg, tuple): # add task
                    self._clean_tasks.append(msg)
                else: # remove task
                    for t in self._clean_tasks:
                        if t[3] == msg:
                            self._clean_tasks.remove(t)
                            break
                q.task_done()

    def schedule(self, callback, *args, **kw):
        """ Schedule `callback` to be called with specified arguments after
watched process terminated. The `callback` must be `pickle`-able.
Returns internal id that can be used to `cancel` the call.
        """
        task_id = self._next_id
        self._next_id = task_id + 1
        q = self._task_queue
        q.put((callback, args, kw, task_id))
        q.join()
        return task_id

    def cancel(self, task_id):
        q = self._task_queue
        q.put(task_id)
        q.join()

    # Some helpers

    def rmtree(self, path, absent_ok = False):
        # XXX: hack for Windows Py2 to support extended-length paths and prevent
        # "WindowsError: [Error 3]".
        # See: https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation
        if os_name == "nt" and PY2:
            path = "\\\\?\\" + path

        if absent_ok:
            return self.schedule(rmtree_existing, path)
        else:
            return self.schedule(rmtree, path)


def rmtree_existing(path):
    if exists(path):
        rmtree(path)


def get_cleaner(*default_args, **default_kw):
    global _current_cleaner

    if _current_cleaner is None:
        _current_cleaner = Cleaner(*default_args, **default_kw)
        _current_cleaner.start()

        # XXX: rough hack for Windows that excludes the cleaner from the
        # children of the current process.
        if os_name == "nt":
            if PY2:
                from multiprocessing import (
                    current_process
                )
                current_process()._children.discard(_current_cleaner)
            else:
                from multiprocessing.process import (
                    _children
                )
                _children.discard(_current_cleaner)

    return _current_cleaner


_current_cleaner = None
