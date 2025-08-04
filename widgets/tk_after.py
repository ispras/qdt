__all__ = [
    "tk_delayed"
  , "tk_periodic"
]


class _tk_after(object):

    def __init__(self, target):
        self.o2id = {}
        self.target = target

    def __get__(self, o, t = None):
        assert t is None
        return self.o2id.get(o)

    def __delete__(self, o):
        cur_id = self.o2id.pop(o, None)
        if cur_id is not None:
            o.after_cancel(cur_id)


class tk_delayed(_tk_after):

    def __set__(self, o, delay):
        o2id = self.o2id
        cur_id = o2id.pop(o, None)
        if cur_id is not None:
            o.after_cancel(cur_id)
        target = self.target
        def call():
            del o2id[o]
            target(o)
        if not delay:
            o2id[o] = o.after_idle(call)
        else:
            o2id[o] = o.after(delay, call)


class tk_periodic(_tk_after):

    def __set__(self, o, delay):
        o2id = self.o2id
        cur_id = o2id.pop(o, None)
        if cur_id is not None:
            o.after_cancel(cur_id)
        target = self.target
        def call():
            target(o)
            o2id[o] = o.after(delay, call)
        o2id[o] = o.after(delay, call)
