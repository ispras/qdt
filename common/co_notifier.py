__all__ = [
    "CoNotifier"
]

from .ml import (
    mlget as _
)
from .co_signal import (
    SignalDispatcherTask,
    CoSignal
)
from .lazy import (
    lazy
)
from os import (
    environ
)


def gen_helpers(sig, event):
    "A function factory that fix values of `sig`."

    if environ.get("DEBUG_CONOTIFIER", False):
        def signalize(*a, **kw):
            print("event: " + event)
            sig.emit(*a, **kw)
    else:
        def signalize(*a, **kw):
            sig.emit(*a, **kw)

    def watch(self, cb):
        sig.watch(cb)

    def unwatch(self, cb):
        sig.unwatch(cb)

    return signalize, watch, unwatch


class CoNotifier(SignalDispatcherTask):
    """ Given an `notifier` instance this task dispatches all event
notifications as coroutine based signals. Provides same API as `notifier`.
    """

    def __init__(self, notifier):
        super(CoNotifier, self).__init__()
        self.description = _(
            "Signal dispatcher for notifier %s" % type(notifier).__name__
        )
        self._events = {}
        for e in notifier.events:
            sig = CoSignal()

            sig.attach(self)
            self._events[e] = sig

            signalize, watch, unwatch = gen_helpers(sig, e)

            notifier.watch(e, signalize)
            # Shortcuts for `watch`/`unwatch` methods.
            setattr(self, "watch_" + e, watch)
            setattr(self, "unwatch_" + e, unwatch)

    @lazy
    def events(self):
        "Tuple of event names."
        return tuple(self._events.keys())

    def watch(self, event, cb):
        "Proxy to `watch` of `CoSignal` for the event."
        self._events[event].watch(cb)

    def unwatch(self, event, cb):
        "Proxy to `unwatch` of `CoSignal` for the event."
        self._events[event].unwatch(cb)
