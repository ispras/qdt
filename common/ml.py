__all__ = [
    "ML"
  , "mlget"
]

from os import (
    name as os_name
)
from sys import (
    version_info as py_version
)
from .formated_string_var import FormatVar

from gettext import (
    translation,
    NullTranslations
)
from locale import getdefaultlocale

from os.path import (
    dirname,
    abspath
)

"""
ML = Multi language
"""

class ML(FormatVar):
    multi_language_strings = []
    current_translation = None

    @staticmethod
    def set_language(locale = None):
        ML.current_translation = None
        locale = [locale] if locale else []
        try:
            # First search for translation in default location
            ML.current_translation = translation("qdc", None, locale,
                codeset = "utf8"
            )
        except:
            try:
                # Else search for translation relative current file path
                localedir = abspath(dirname(__file__) + "/../locale")
                ML.current_translation = translation(
                    "qdc",
                    localedir,
                    locale,
                    codeset = "utf8"
                )
            except:
                pass

        if not ML.current_translation:
            # If translation was found then the keys is used for strings
            ML.current_translation = NullTranslations()

        for s in ML.multi_language_strings:
            s.update()

    def __init__(self, value, **kwargs):
        FormatVar.__init__(self, **kwargs)
        self.key_value = value

        self.update()
        ML.multi_language_strings.append(self)

    if os_name == "nt" and py_version[0] == 3:
        # lgettext returns RAW bytes and Python 3(.5) is known to have troubles
        # with this under Windows (7 SP1 64 bit).
        def update(self):
            raw = ML.current_translation.lgettext(self.key_value)
            self.set(raw.decode("utf8"))
    else:
        def update(self):
            self.set(ML.current_translation.lgettext(self.key_value))

def mlget(key_value):
    for mls in ML.multi_language_strings:
        if mls.key_value == key_value:
            return mls

    return ML(key_value)

current_locale, encoding = getdefaultlocale()
ML.set_language(current_locale)
