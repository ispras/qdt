__all__ = [
    "SignalIsAlreadyAttached"
  , "SignalIsNotAttached"
  , "SignalDispatcherTask"
  , "CoSignal"
]

from .co_dispatcher import (
    CoTask
)
from .ml import (
    mlget as _
)
from .notifier import (
    Notifier
)
from sys import (
    exc_info
)

class SignalIsAlreadyAttached(RuntimeError):
    pass

class SignalIsNotAttached(RuntimeError):
    pass

@Notifier("failed")
class SignalDispatcherTask(CoTask):
    def __init__(self):
        CoTask.__init__(
            self,
            self.co_deliver(),
            description = _("Signal Dispatcher failed")
        )
        self.queue = []

    def co_deliver(self):
        while True:
            queue = self.queue

            if not queue:
                yield False
                continue

            # Prevent queue feeding during dispatching.
            self.queue = []

            while queue:
                listeners, args, kw = queue.pop(0)

                while listeners:
                    yield True

                    try:
                        l = listeners.pop(0)
                        if args is None:
                            if kw is None:
                                l()
                            else:
                                l(**kw)
                        elif kw is None:
                            l(*args)
                        else:
                            l(*args, **kw)
                    except BaseException as e:
                        self.__notify_failed(e, exc_info()[2])


    def _do_emit(self, signal, args, kw):
        listeners = signal.listeners
        if not listeners:
            return

        self.queue.append((list(listeners), args, kw))

class CoSignal(object):
    def __init__(self):
        self.listeners = set()
        self.disp = None

    def attach(self, dispatcher):
        if self.disp:
            raise SignalIsAlreadyAttached()
        self.disp = dispatcher

        return self

    def detach(self):
        if self.disp is None:
            raise SignalIsNotAttached()
        self.disp = None

        return self

    def emit_args(self, args, kw):
        try:
            self.disp._do_emit(self, args, kw)
        except AttributeError:
            raise SignalIsNotAttached()

        return self

    def emit(self, *args, **kw):
        return self.emit_args(args, kw)

    def watch(self, callback):
        self.listeners.add(callback)

        return self

    def unwatch(self, callback):
        self.listeners.remove(callback)

        return self
