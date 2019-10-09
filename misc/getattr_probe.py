""" Experiments under `__getattr__`.
"""

class GAProbe(object):

    def __init__(self):
        self.existing = object()

    def __getattr__(self, name):
        print("__getattr__ %s" % name)
        ret = object()
        self.__dict__[name] = ret
        return ret


if __name__ == "__main__":
    from sys import (
        version_info
    )

    print(version_info)

    gap = GAProbe()

    gap.existing
    # Does not result in `__getattr__` call because `existing` is in
    # the `__dict__`

    gap.not_existing
    # Does result in `__getattr__` because `not_existing` is not in the
    # `__dict__`.

    gap.not_existing
    # Does not result in `__getattr__` because `not_existing` has been
    # added to `__dict__` by previous `__getattr__` call.
