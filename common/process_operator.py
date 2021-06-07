__all__ = [
    "ProcessOperator"
      , "ProcessCoOperator"
]

from subprocess import (
    Popen,
    PIPE,
)
from threading import (
    Thread,
    Lock,
    Event,
)
from time import (
    time,
)


class ProcessOperator(object):

    def operate(self):
        """ Called on each input from the process (stdout & stderr).

Look `self.history` for the data entries.
Each entry is an iterable:
    0: index of stream: 1 - stdout, 2 - stderr
    1: data, an zero length if EOF (relies on `BufferedIOBase.read`)
Entries are only appended at runtime.
        """

    def finished(self):
        "Called when both stdout & stderr are closed."

    def terminate(self):
        return self._p.terminate()

    def wait_threads(self, timeout = None):
        "Returns `True` iff all threads finished."
        if timeout is None:
            for t in self._threads:
                t.join(timeout)
                assert not t.isAlive()
            return True

        t0 = time()
        for t in self._threads:
            t.join(timeout)

            if t.isAlive():
                return False

            t1 = time()
            timeout -= t1 - t0

            if timeout <= 0.0:
                return False

            t0 = t1

        return True

    @property
    def returncode(self):
        return self._p.returncode

    @property
    def wait(self):
        return self._p.wait

    def __init__(self, *popen_args, **popen_kw):
        popen_kw["stdout"] = popen_kw["stderr"] = popen_kw["stdin"] = PIPE

        self._p = p = Popen(*popen_args, **popen_kw)

        self.stdin = p.stdin

        stdout_over, stderr_over = Event(), Event()

        threads = list(
            Thread(target = self._stream_reader, args = args) for args in [
                (1, p.stdout, stdout_over),
                (2, p.stderr, stderr_over),
            ]
        )
        threads.append(
            Thread(
                target = self._operator,
                args = (stdout_over, stderr_over),
            )
        )

        self._threads = threads

        # communication lock
        self._comm_lock = Lock()
        # notification for operator
        self._event = Event()
        self.history = []

        for t in threads:
            t.start()

    def _operator(self, stdout_over, stderr_over):
        wait = self._event.wait
        lock = self._comm_lock

        while not (stdout_over.is_set() and stderr_over.is_set()):
            wait()

            with lock:
                self.operate()

        self.finished()

    def _stream_reader(self, idx, stream, over):
        read = stream.read
        lock = self._comm_lock
        history = self.history
        event = self._event

        while True:
            data = read()
            with lock:
                history.append((idx, data))

            # empty data is EOF
            if not data:
                over.set()
                # exactly after `over` event
                event.set()
                break

            event.set()


class ProcessCoOperator(ProcessOperator):

    def co_operate(self):
        """ Gets control at startup and on each input from the process.

 Not-`None` values `yield`ed are written to the process stdin.

`yield` returns iterable of two items:
    0: data of stdout or `None` if current input is from stderr
    1: data of stderr or `None` if current input is from stdout
Data is zero length if EOF of the corresponding stream reached (relies on
`BufferedIOBase.read`)
        """
        yield # Must be a coroutine

    def __init__(self, *a, **kw):
        super(ProcessCoOperator, self).__init__(*a, **kw)

        self._co_operator = self._co_operator()

    def operate(self):
        try:
            next(self._co_operator)
        except StopIteration:
            pass

    def _co_operator(self):
        operate = self.co_operate()

        write = self.stdin.write

        try:
            ret = next(operate)
        except StopIteration:
            return

        if ret is not None:
            write(ret)

        history_index = 0
        history = self.history

        while True:
            if history_index == len(history):
                yield
                continue

            idx, data = history[history_index]
            history_index += 1

            if idx == 1:
                arg = data, None
            else: # idx == 2
                arg = None, data

            try:
                ret = operate.send(arg)
            except StopIteration:
                break

            if ret is not None:
                write(ret)
