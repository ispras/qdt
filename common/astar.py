__all__ = [
    "a_iter_reversed"
  , "CoAStep"
  , "co_a_star"
  , "CoAWorseStep"
  , "CoStepForbidden"
]


from bisect import (
    insort,
)


class CoAStep:

    def __iter_steps__(self):
        raise NotImplementedError

    def __co_try_end__(self):
        raise NotImplementedError

    def __lt__(self, step):
        raise NotImplementedError

    def iter_reversed(self):
        return a_iter_reversed(self)

    def a_star_path_str(self, sep = " <- "):
        return sep.join(map(str, a_iter_reversed(self)))

    __a_prev__ = None

    def co_a_star(self):
        return co_a_star(self)


def co_a_star(start):
    frontier = [start]
    pop = frontier.pop

    while frontier:
        s = pop(0)

        if (yield s.__co_try_end__()):
            break

        yield True
        for ns in s.__iter_steps__():
            yield True
            ns.__a_prev__ = s
            insort(frontier, ns)
            yield True


def a_iter_reversed(s):
    while s is not None:
        yield s
        s = s.__a_prev__


class CoStepForbidden(BaseException):
    "not an excetion"


class CoAWorseStep(CoAStep):

    w = 0

    def __step_penalty__(self, p):
        """
@param p:
    A `p`oint for next step.

@return penalty for stepping
@raise CoStepForbidden:
    The `p`oint is unacceptable.
        """
        raise NotImplementedError

    def __iter_points__(self):
        raise NotImplementedError

    def __lt__(self, o):
        return self.w < o.w

    def __init__(self, p):
        self.p = p

    def __iter_steps__(self):
        cls = type(self)
        w = self.w
        for p in self.__iter_points__():
            try:
                sw = self.__step_penalty__(p)
            except CoStepForbidden:
                continue
            s = cls(p)
            s.w = w + sw
            yield s
