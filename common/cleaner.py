__all__ = [
    "Cleaner"
  , "get_cleaner"
]


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


if os_name == "nt":
    def demonize():
        pass
else:
    from os import (
        fork,
        setpgrp
    )
    from os import (
        _exit
    )
    def demonize():
        """ Turns process into something between normal process and
UNIX daemon. I.e. it's a "light" form of demonization.
        """
        # Normally, Python process waits for all children.
        # Cleaner is a child, so the parent process does not terminate when
        # its main thread ends or raises an exception.
        # The parent can use os._exit or terminate itself using other way.
        # But we want the parent does not worry about it.
        # The child is terminates itself after making fork of self.
        # Using this hack the cleaner (child) is alive and its parent process
        # can terminate in a usual way.
        # https://stackoverflow.com/questions/473620/how-do-you-create-a-daemon-in-python
        if fork():
            _exit(0)

        # Normally, if parent process terminated, all its children are
        # terminated too. But Cleaner must survive to clean things after
        # its parent.
        # See: https://stackoverflow.com/questions/6011235/run-a-program-from-python-and-have-it-continue-to-run-after-the-script-is-kille
        setpgrp()


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

        for t, a, kw, _ in self._clean_tasks:
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
        if absent_ok:
            return self.schedule(rmtree_existing, path)
        else:
            return self.schedule(rmtree, path)


def rmtree_existing(path):
    if exists(path):
        rmtree(path)


def get_cleaner(*defult_args, **default_kw):
    global _current_cleaner

    if _current_cleaner is None:
        _current_cleaner = Cleaner(*defult_args, **default_kw)
        _current_cleaner.start()

    return _current_cleaner


_current_cleaner = None
