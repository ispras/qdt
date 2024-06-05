__all__ = [
    "UserSettings"
]

from .persistent import (
    Persistent,
)

from os.path import (
    expanduser,
    isfile,
    join,
)


class UserSettings(Persistent):

    @property
    def _suffix(self):
        raise NotImplementedError(
            "Suffix for user settings file name is not defined by %s" % (
                type(self).__name__
            )
        )

    _prefixes = (
        expanduser("~"),
        # append legacy prefixes in subclasses
    )

    def __init__(self, **kw):
        suffix = self._suffix

        for i, prefix in enumerate(self._prefixes):
            file_name = join(prefix, suffix)
            if isfile(file_name):
                break
        else:
            file_name = join(self._prefixes[0], suffix)

        super(UserSettings, self).__init__(file_name, **kw)

        if i > 0:
            # re-save to preferable location
            with self:
                self._file_name = join(self._prefixes[0], suffix)
