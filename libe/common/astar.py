__all__ = [
    "a_iter_reversed"
  , "CoAStep"
  , "co_a_star"
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

    def a_star_path_str(self, sep = " <- "):
        return sep.join(map(str, a_iter_reversed(self)))

    __a_prev__ = None


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
