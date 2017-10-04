#!/usr/bin/python
# coding=utf-8
# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :

from argparse import \
    ArgumentParser

import sys

from re import \
    compile

from itertools import \
    count

from collections import \
    OrderedDict

class PosInfo(object):
    def __init__(self, row, start, end, m):
        self.row, self.start, self.end, self.m = row, start, end, m

class PatchInfo(PosInfo):
    def __init__(self, *args):
        super(PatchInfo, self).__init__(*args)

        self.name = self.m.group("name")
        try:
            self.type, self.tag = self.name.split(".")
        except:
            self.tag = self.name
            self.type = None
        else:
            if self.type == "":
                self.type = None
                self.tag = self.name

        self.substitution = None

    def patch(self, lines):
        s = self.substitution
        if s is None:
            return

        l = lines[self.row]

        m = self.m

        l.patch(m.start("substitution"), m.end("substitution"), s)

class AnchorInfo(PatchInfo):
    def __init__(self, *args):
        super(AnchorInfo, self).__init__(*args)

        self.references = []

class RefInfo(PatchInfo):
    def __init__(self, *args):
        super(RefInfo, self).__init__(*args)

        self.anchors = []

if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("in_file_name", nargs = "?", metavar = "in-file-name")
    ap.add_argument("--out-file-name", "-o", nargs = "?")
    ap.add_argument("--ispras", action = 'store_true')

    args = ap.parse_args()

    ispras = args.ispras

    try:
        in_file_name = args.in_file_name
    except:
        in_file = sys.stdin
    else:
        in_file = open(in_file_name, "rb")


    out_file_name = args.out_file_name
    if out_file_name is None:
        out_file = sys.stdout
        log_file = sys.stderr
    else:
        out_file = open(out_file_name, "wb")
        log_file = sys.stdout

    def log(msg):
        log_file.write(msg + "\n")

    anchor = compile("""\
(?P<substitution2>\$?)\
(?(substitution2)[^<]*)\
(?P<prefix>< *a +name *= *)\
(?P<quote>["'])\
(?P<name>.*?)\
(?P=quote)\
(?P<infix> *>[^\$<]*)\
(?P<substitution1>\$?)\
(?P<suffix>[^<]*< */ *a *>)\
"""
    )

    reference = compile("""\
(?P<prefix>\[)\
(?P<substitution1>\$?)\
(?P<infix>]\(#)\
(?P<name>[^\)]+)\
(?P<suffix>\))\
"""
    )

    anchors = OrderedDict()
    references = []
    lines = []

    for row, l in enumerate(iter(in_file.readline, "")):
        lines.append(l)

        col = 0
        while True:
            m = anchor.search(l, col)

            if m is not None:
                start, col = m.regs[0]

                anchors[m.group("name")] = AnchorInfo(row, start, col, m)

                log(str(row) + "." + str(start) + " anchor : "
                    + str(m.groupdict())
                )
                continue

            m = reference.search(l, col)
            if m is not None:
                start, col = m.regs[0]

                references.append(RefInfo(row, start, col, m))

                log(str(row) + "." + str(start) + " reference : "
                    + str(m.groupdict())
                )
                continue

            break

    in_file.close()

    # link anchors and references
    for ref in references:
        try:
            anchor = anchors[ref.name]
        except KeyError:
            continue

        ref.anchors.append(anchor)
        anchor.references.append(ref)

    source_num_gen = count(1)

    # выше/ниже, использованные источники
    for ref in references:
        la = len(ref.anchors)
        if ref.type == "rel":
            if la == 0:
                log("no anchors found for relative reference " + ref.tag)
                continue
            elif la > 1:
                log("too many (%u) anchors found for relative reference %s" % (
                    la, ref.tag
                ))

            a = ref.anchors[0]
            if a.row == ref.row:
                if a.start < ref.start:
                    ref.substitution = "выше"
            elif a.row < ref.row:
                ref.substitution = "выше"
            else:
                ref.substitution = "ниже"
        elif ref.type == "ref":
            if la == 0:
                log("no anchors found for reference " + ref.tag)
                continue
            elif la > 1:
                log("too many (%u) anchors found for reference %s" % (
                    la, ref.tag
                ))

            a = ref.anchors[0]
            if a.substitution is None:
                a.substitution = str(next(source_num_gen))
            ref.substitution = a.substitution
        elif ref.type == "pic":
            pass
        elif ref.type == "tbl":
            pass
        elif ref.type is not None:
            log("unknown reference type %s at %u.%u" % (
                ref.type, ref.row, ref.start
            ))

    picture_num_gen = count(1)
    table_num_gen = count(1)

    for a in anchors.values():
        if a.type == "rel":
            pass
        elif a.type == "ref":
            pass
        elif a.type == "pic":
            a.substitution = str(next(picture_num_gen))
            for ref in a.references:
                ref.substitution = a.substitution
        elif a.type == "tbl":
            a.substitution = str(next(table_num_gen))
            for ref in a.references:
                ref.substitution = a.substitution
        elif a.type is not None:
            log("unknown anchor type %s at %u.%u" % (
                a.type, a.row, a.start
            ))

    # patch lines
    for row, line in enumerate(list(lines)):
        pis = [ pi for pi in references + anchors.values() if pi.row == row ]

        if not pis:
            continue

        pis = sorted(pis, key = lambda pi :-pi.start)

        for pi in pis:
            if pi.type == "pic":
                pass
            if pi.substitution is None:
                continue

            m = pi.m

            for s in count(1):
                subst = "substitution%u" % s
                try:
                    g = m.group(subst)
                except IndexError:
                    break
                if g:
                    line = line[:m.start(subst)] \
                        + pi.substitution \
                        + line[m.end(subst):]

        lines[row] = line

    # sort sources by reference order
    ref_anchors = [ a for a in anchors.values() if \
        a.type == "ref" and a.substitution is not None
    ]

    ref_anchors = sorted(ref_anchors, key = lambda a : int(a.substitution))

    min_row = len(lines)

    a_lines = []
    for a in ref_anchors:
        if a.row < min_row:
            min_row = a.row

        for row in count(a.row):
            for other_a in ref_anchors:
                if other_a is a:
                    continue
                if other_a.row == row:
                    # other anchor reached
                    break
            else:
                # this row does not belong to other anchor
                try:
                    line = lines[row]
                except IndexError:
                    # EOF reached
                    break
                a_lines.append(line)
                continue
            # other anchor reached (see above)
            break

    lines = lines[:min_row] + a_lines

    # automatic chapter enumeration
    if ispras:
        levels = [0]

        for idx, l in enumerate(list(lines)):
            if l[0] != "#":
                continue
            if "$" not in l:
                continue

            parts = l.split("$")

            current = len(levels)

            line_level = len(parts) - 1

            for tmp in range(current, line_level):
                levels.append(0)

            for tmp in range(line_level, current):
                levels.pop()

            levels[line_level - 1] += 1

            new_line = ""
            for p, l in zip(parts, levels):
                new_line += p + str(l)

            new_line += parts[-1]

            lines[idx] = new_line

    for l in lines:
        out_file.write(str(l))

    out_file.close()
