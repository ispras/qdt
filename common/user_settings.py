__all__ = [
    "UserSettings"
]


from .persistent import (
    Persistent,
)
from os.path import (
    expanduser,
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

    def __init__(self, **kw):
        file_name = expanduser(join("~", self._suffix))
        super(UserSettings, self).__init__(file_name, **kw)
