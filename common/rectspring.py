__all__ = [
    "RectSpring"
]


class RectSpring:
    """ Generates points `(x, y)` in rectangular spring form.
Assumes screen coordinates (`y` grows to the bottom).
Spring is clockwise.
    """

    def __init__(self, stepx,
        x = 0, y = 0,
        w = 0, h = 0,
        stepy = None,
    ):
        if stepy is None:
            stepy = stepx
        self.stepx, self.stepy = stepx, stepy
        self.l, self.t, self.r, self.b = x, y, (x + w), (y + h)
        self.x, self.y = x, y
        self._step = self._step_r

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.x, self.y
        finally:
            self._step()

    def _step_r(self):
        self.x = x = self.x + self.stepy
        if self.r < x:
            self.r = x
            self._step = self._step_b

    def _step_b(self):
        self.y = y = self.y + self.stepy
        if self.b < y:
            self.b = y
            self._step = self._step_l

    def _step_l(self):
        self.x = x = self.x - self.stepy
        if x < self.l:
            self.l = x
            self._step = self._step_t

    def _step_t(self):
        self.y = y = self.y - self.stepy
        if y < self.t:
            self.t = y
            self._step = self._step_r

    def __getstate__(self):
        s = dict(self.__dict__)
        s["_step"] = s["_step"].__name__
        return s

    def __setstate__(self, s):
        s["_step"] = getattr(self, s["_step"])
        self.__dict__.update(s)
