#!/usr/bin/python2

from subprocess import \
    call

from os import \
    makedirs

from os.path import \
    join, \
    isdir, \
    isfile

files = [
    join("widgets", "device_settings.py"),
    join("widgets", "device_settings_window.py"),
    join("widgets", "device_tree_widget.py"),
    join("widgets", "irq_settings.py"),
    join("widgets", "machine_diagram_widget.py"),
    join("widgets", "pci_device_settings.py"),
    join("widgets", "settings_window.py"),
    join("widgets", "sysbusdevset.py"),
    join("widgets", "hotkey.py"),
    join("widgets", "bus_settings.py"),
    join("qdc-gui.py"),
    join("history-test.py")
]

langs = [
    "ru_RU"
]

for l in langs:
    directory = join("locale", l, "LC_MESSAGES")
    if not isdir(directory):
        makedirs(directory)

    call(
        [   "xgettext",
            "-o", join(directory, "messages.po"),
        ] + files
    )

    if not isfile(join(directory, "qdc.po")):
        call(
            [   "mv",
                join(directory, "messages.po"),
                join(directory, "qdc.po")
            ]
        )
    else:
        call(
            [   "msgmerge",
                "-U",
                "-N", join(directory, "qdc.po"),
                join(directory,"messages.po")
            ]
        )
        call(
            [   "rm",
                join(directory, "messages.po")
            ]
        )

    call(
        [
            "msgfmt",
            "-o", join(directory, "qdc.mo"),
            join(directory, "qdc.po")
        ]
    )
