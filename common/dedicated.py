__all__ = [
    "Dedicated"
]

from multiprocessing import (
    Pipe,
    Process
)
from traceback import (
    format_exc,
    print_exc,
)


class StopDedicated(BaseException): pass
class NoRunningCalls(RuntimeError): pass

class InternalFailure: pass
class TargetReturned: pass
class TargetTimeout(TimeoutError): pass
class TargetFailed: pass


class Dedicated(Process):
    """ It `launch`es (i.e. `__call__`s) callable `target`s in
a `Dedicated` `Process`.
    """

    def __init__(self, start = True):
        self._front, back = Pipe()
        super(Dedicated, self).__init__(
            args = (
                back,
            ),
        )
        if start:
            self.start()
        self._running = 0

    def launch(self, *target_and_a, **kw):
        self._front.send((target_and_a, kw))
        self._running += 1

    def poll(self, timeout = None):
        r = self._running
        if r < 1:
            raise NoRunningCalls
        if timeout:
            if self._front.poll(timeout):
                res = self._front.recv()
            else:
                raise TargetTimeout
        else:
            res = self._front.recv()
        self._running = r - 1
        code, res, *tail = res
        if code is TargetReturned:
            return res
        if code is InternalFailure:
            raise code(res, *tail)
        else:  # TargetFailed
            # If `TargetFailed`, original exception should be `raise`d.
            # `res` is the original exception class.
            # The `*tail` should not be passed to original exception
            # constructor beecause it has arbitrary nature.
            # Hence to provide the `*tail` to a user, the exceptions are
            # stacked.
            try:
                raise code(res, *tail)
            except:
                raise res

    def __call__(self, *a, **kw):
        self.launch(*a, **kw)
        while self._running:
            ret = self.poll()
        return ret

    def stop(self, clean = True):
        self.launch(self.stop_dedicated)
        if not clean:
            return
        if clean is True:
            self.join()
        else:
            self.join(clean)
        try:
            return self.exitcode
        finally:
            self.close()

    @staticmethod
    def stop_dedicated():
        raise StopDedicated

    def run(self):
        back, = self._args
        recv = back.recv
        send = back.send
        while True:
            try:
                task = recv()
            except BaseException as e:
                send((InternalFailure, type(e), format_exc()))
                break
            (target, *a), kw = task
            try:
                ret = target(*a, **kw)
            except StopDedicated:
                break
            except BaseException as e:
                try:
                    send((TargetFailed, type(e), format_exc()))
                except:
                    print_exc()
                    break
            try:
                send((TargetReturned, ret))
            except:
                print_exc()
                break
