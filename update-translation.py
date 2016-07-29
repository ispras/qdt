#!/usr/bin/python2

from subprocess import call
import os

files = [
    "widgets/device_settings.py",
    "widgets/machine_widget.py",
    "history-test.py",
    "qdc-gui.py",
    "widgets/hotkey.py"
]

langs = [
    "ru_RU"
]

for l in langs:
    directory = "locale/" + l + "/LC_MESSAGES/"
    if not os.path.isdir(directory):
        os.makedirs(directory)

    call(
        [   "xgettext",
            "-o", directory + "messages.po",
        ] + files
    )

    if not os.path.isfile(directory + "qdc.po"):
        call(
            [   "mv",
                directory + "messages.po",
                directory + "qdc.po"
            ]
        )
    else:
        call(
            [   "msgmerge",
                "-U",
                "-N", directory + "qdc.po",
                directory + "messages.po"
            ]
        )
        call(
            [   "rm",
                directory + "messages.po"
            ]
        )

    call(
        [
            "msgfmt",
            "-o", directory + "qdc.mo",
            directory + "qdc.po"
        ]
    )