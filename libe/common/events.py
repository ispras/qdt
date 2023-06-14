__all__ = [
    "ALL"
  , "dismiss"
  , "iter_notify"
      , "notify"
  , "listen"
]


from collections import (
    defaultdict,
)
from traceback import (
    print_exc,
)

# event -> callback (listener)
_event_listeners = lambda : defaultdict(set)
# notifier -> ...
_listeners = defaultdict(_event_listeners)
# event -> notifiers
_event_notifiers = _event_listeners
# callback (listener) ->
_notifiers = defaultdict(_event_notifiers)

_empty = dict()
class ALL: pass


# cache
_get_el = _listeners.get
_get_en = _notifiers.get
_pop_en = _notifiers.pop


# Note, `get`/`pop` should not trigger `defaultdict`'s factory callback.
# _get_en(0, None); assert not _notifiers
# _pop_en(0, None); assert not _notifiers


def listen(notifier, event, callback):
    _listeners[notifier][event].add(callback)
    _notifiers[callback][event].add(notifier)

    _listen(notifier, event, callback)


def dismiss(callback, event = ALL, notifier = ALL):
    if event is ALL:
        if notifier is ALL:
            for e, ns in _pop_en(callback, _empty).items():
                for n in ns:
                    _listeners[n][e].discard(callback)
                    _dismiss(callback, e, n)
        else:
            _el = _listeners[notifier]
            for e, ns in _get_en(callback, _empty).items():
                _el[e].discard(callback)
                ns.discard(notifier)
                _dismiss(callback, e, notifier)
    else:
        if notifier is ALL:
            for n in _get_en(callback, _empty).pop(event, _empty):
                _listeners[n][event].discard(callback)
                _dismiss(callback, event, n)
        else:
            _listeners[notifier][event].discard(callback)
            _notifiers[callback][event].discard(notifier)
            _dismiss(callback, event, notifier)


def iter_notify(notifier, event, *a, **kw):
    for cb in tuple(_get_el(notifier, _empty).get(event, _empty)):
        try:
            ret = cb(*a, **kw)
        except BaseException as ret:
            pass  # `dismiss(cb, ...)` can be done by the caller.
        yield cb, ret


def notify(notifier, event, *a, **kw):
    for cb in tuple(_get_el(notifier, _empty).get(event, _empty)):
        try:
            cb(*a, **kw)
        except:
            dismiss(cb, event = event, notifier = notifier)
            raise


def _listen(c, e, n):
    try:
        notify(c, "listens", e, n)
    except:
        print_exc()  # don't blame caller, only notify user

    try:
        notify(n, "listened", e, c)
    except:
        print_exc()  # too


def _dismiss(c, e, n):
    try:
        notify(c, "dismissed", e, n)
    except:
        print_exc()  # too
    try:
        notify(n, "dismisses", e, c)
    except:
        print_exc()  # too
