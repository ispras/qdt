from Tkinter import StringVar
import gettext
import locale

"""
ML = Multi language
"""

class ML(StringVar):
    multi_language_strings = []
    current_translation = None

    @staticmethod
    def set_language(locale = None):
        ML.current_translation = gettext.translation(
            "qdc",
            "/home/real/work/qemu/device_creator/src/locale/",
            [locale] if locale else []
        )
        for s in ML.multi_language_strings:
            s.update()

    def __init__(self, value, **kwargs):
        StringVar.__init__(self, **kwargs)
        self.key_value = value

        self.update()
        ML.multi_language_strings.append(self)

    def update(self):
        self.set(ML.current_translation.lgettext(self.key_value))

current_locale, encoding = locale.getdefaultlocale()
ML.set_language(current_locale)