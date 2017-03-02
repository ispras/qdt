from .formated_string_var import \
    FormatVar

from gettext import \
    translation, \
    NullTranslations

from locale import \
    getdefaultlocale

from os.path import \
    dirname, \
    abspath

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
            ML.current_translation = translation("qdc", None, locale)
        except:
            try:
                # Else search for translation relative current file path
                localedir = abspath(dirname(__file__) + "/../locale")
                ML.current_translation = translation(
                    "qdc",
                    localedir,
                    locale
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

    def update(self):
        self.set(ML.current_translation.lgettext(self.key_value))

def mlget(key_value):
    for mls in ML.multi_language_strings:
        if mls.key_value == key_value:
            return mls

    return ML(key_value)

current_locale, encoding = getdefaultlocale()
ML.set_language(current_locale)
