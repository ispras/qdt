__all__ = [
    "ObjectObserver"
]

# yet another
""" Event notification mechanism.
"""

class Observed(dict):

    def __init__(self, obj):
        self._obj = obj

    def __missing__(self, event):
        cbs = list()
        self[event] = cbs
        return cbs


class ObjectObserver(dict):

    def __missing__(self, obj):
        ret = Observed(obj)
        self[obj] = ret
        return ret

    def observe(self, cb, obj, *events):
        event2cbs = self[obj]
        if events:
            for event in events:
                event2cbs[event].append(cb)
        else:
            event2cbs[None].append(cb)

    def forget(self, cb, *obj_and_events):
        if not obj_and_events:
            for obj in tuple(self):
                self.forget(cb, obj)
            return
        obj, *events = obj_and_events
        event2cbs = self.pop(obj, None)
        if event2cbs is None:
            return
        pop = event2cbs.pop
        if not events:
            events = tuple(event2cbs)
        for event in events:
            cbs = pop(event, None)
            if cbs is None:
                continue
            try:
                cbs.remove(cb)
            except ValueError:
                pass
            if cbs:
                event2cbs[event] = cbs
        if event2cbs:
            self[obj] = event2cbs

    def emit(self,obj, *events, **kw):
        event2cbs = self.pop(obj, None)
        if event2cbs is None:
            return
        pop = event2cbs.pop
        for event in events:
            cbs = pop(event, None)
            if cbs is None:
                continue
            cbs2 = list()
            again = cbs2.append
            for cb in cbs:
                if cb(**kw):
                    again(cb)
            if cbs2:
                event2cbs[event] = cbs2
        cbs = pop(None, None)
        if cbs is not None:
            kw["events"] = events
            cbs2 = list()
            again = cbs2.append
            for cb in cbs:
                if cb(**kw):
                    again(cb)
            if cbs2:
                event2cbs[None] = cbs2
        if event2cbs:
            self[obj] = event2cbs

    __call__ = emit
