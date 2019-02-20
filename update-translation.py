#!/usr/bin/python

from subprocess import (
    call
)
from os import (
    walk,
    makedirs
)
from os.path import (
    dirname,
    join,
    isdir,
    isfile,
)
from re import (
    compile
)
from collections import (
    OrderedDict
)


locale_files = OrderedDict()
# Using of explicitly set (b)inary modifier for the pattern is required to
# support both Py2 and Py3.
# Note that files are also opened in (b)inary mode to avoid any internal
# decoding.
ml_pattern = compile(b" mlget +as +_[, \n]")

root_dir = dirname(__file__) or '.'
root_prefix_len = len(root_dir) + 1

for root, dirs, files in walk(root_dir):
    for file in files:
        if file[-3:] != ".py":
            continue

        file_name = join(root, file)
        f = open(file_name, "rb")
        lines = list(f.readlines())
        f.close()

        for line in lines:
            if ml_pattern.search(line):
                break
        else:
            continue

        locale_files[file_name] = file_name[root_prefix_len:]


locale_files = OrderedDict(
    (full, locale_files[full]) for full in sorted(locale_files)
)


langs = [
    "en_US",
    "ru_RU"
]

print("Root directory: " + root_dir)
print("Updating *.po file by those files:")
for f in locale_files.values():
    print("    " + f)
print("...")

for l in langs:
    directory = join(root_dir, "locale", l, "LC_MESSAGES")
    if not isdir(directory):
        makedirs(directory)

    messages_po = join(directory, "messages.po")
    qdc_po = join(directory, "qdc.po")

    call(["xgettext", "-o", messages_po] + list(locale_files.keys()))

    if isfile(qdc_po):
        call(["msgmerge", "-U", "-N", qdc_po, messages_po])
        call(["rm", messages_po])
    else:
        call(["mv", messages_po, qdc_po])

    # Post process .po file:
    # - replace full file names with source root relative names
    # - one file name per line
    # replacement is binary, so first encode file mapping
    replacements = OrderedDict(
        (full.encode("utf-8"), short.encode("utf-8"))
        for (full, short) in locale_files.items()
    )

    with open(qdc_po + ".tmp", "wb") as po_out:
        with open(qdc_po, "rb") as po_in:
            for l in po_in.readlines():
                if l.startswith(b"#: "):
                    l = l[3:].rstrip()
                    for l in l.split(b" "):
                        for full, short in replacements.items():
                            i = l.find(full)
                            if i < 0:
                                continue
                            l = l[:i] + short + l[i + len(full):]
                            break
                        po_out.write(b"#: " + l + b"\n")
                else:
                    po_out.write(l)

    call(["mv", qdc_po + ".tmp", qdc_po])

    call(["msgfmt", "-o", join(directory, "qdc.mo"), qdc_po])
