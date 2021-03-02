__all__ = [
    "EPS"
]


from time import (
    time,
)


class EPS(object):
    "Events Per Second counter"

    __slots__ = (
        "_events",
        "_fevents",
        "_mem",
        "_ptr",
    )

    def __init__(self, events = 20):
        events = max(2, events)

        self._events = events
        self._fevents = float(events)
        self._mem = [time()] * events

        # Points to recent events time stamp in the _mem.
        # Decrement counter is used because of Python's negative array indexing
        # feature (see `get`).
        # I.e. (ptr - 1) is always points to elder time stamp.
        self._ptr = 0

    def event(self):
        ptr = self._ptr - 1
        self._mem[ptr] = time()

        if ptr < 0:
            self._ptr = self._events - 1
        else:
            self._ptr = ptr

    def get(self):
        ptr = self._ptr
        mem = self._mem
        try:
            return self._fevents / (mem[ptr] - mem[ptr - 1])
        except ZeroDivisionError:
            # No `events`s yet.
            return 0.0

    def __call__(self):
        self.event()
        return self.get()
