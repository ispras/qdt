#!/usr/bin/python2

from subprocess import call
import os

files = [
    "qdc-gui.py"
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
                "-N", directory + "qdc.po",
                directory + "messages.po",
                "-o" , directory + "new.po"
            ]
        )
        call(
            [   "rm",
                directory + "messages.po"
            ]
        )

    call(
        [   "mv",
            directory + "new.po",
            directory + "qdc.po"
        ]
    )

    call(
        [
            "msgfmt",
            "-o", directory + "qdc.mo",
            directory + "qdc.po"
        ]
    )