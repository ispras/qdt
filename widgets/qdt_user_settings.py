__all__ = [
    "QDTUserSettings",
]

from common import (
    qdtdirs,
    UserSettings,
)


class QDTUserSettings(UserSettings):

    _prefixes = (
        qdtdirs.user_cache_dir,
    ) + UserSettings._prefixes
