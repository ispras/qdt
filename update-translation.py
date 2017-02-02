#!/usr/bin/python2

from subprocess import call
import os

files = [
    "widgets/device_settings.py",
    "widgets/device_settings_window.py",
    "widgets/device_tree_widget.py",
    "widgets/irq_settings.py",
    "widgets/machine_diagram_widget.py",
    "widgets/pci_device_settings.py",
    "widgets/settings_window.py",
    "widgets/sysbusdevset.py",
    "widgets/hotkey.py",
    "widgets/bus_settings.py",
    "qdc-gui.py",
    "history-test.py"
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
