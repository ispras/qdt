__all__ = [
    "ML"
  , "mlget"
]

from sys import (
    version_info as py_version
)
from .formated_string_var import (
    FormatVar
)
from gettext import (
    translation,
    NullTranslations
)
from locale import (
    getdefaultlocale
)
from os.path import (
    dirname,
    abspath
)

"""
ML = Multi language
"""

class ML(FormatVar):
    multi_language_strings = {}
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

        for s in ML.multi_language_strings.values():
            s.update()

    def __init__(self, value, **kwargs):
        FormatVar.__init__(self, **kwargs)
        self.key_value = value

        self.update()
        ML.multi_language_strings[value] = self

    if py_version[0] == 3:
        def update(self):
            val = ML.current_translation.gettext(self.key_value)
            # Previously used `lgettext` has been seen in at most Py3.10.
            # Moreover, Py3 doc recomends to avoid using l-prefixed functions.
            self.set(val)
    else:
        def update(self):
            raw = ML.current_translation.lgettext(self.key_value)
            trans = raw if isinstance(raw, unicode) else raw.decode("utf8")
            self.set(trans)

def mlget(key_value):
    if key_value in ML.multi_language_strings:
        return ML.multi_language_strings[key_value]
    else:
        return ML(key_value)

current_locale, encoding = getdefaultlocale()
ML.set_language(current_locale)
