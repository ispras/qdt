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

class Line(object):
    def __init__(self, line):
        self.pieces = [str(line)]
        self.mapping = [(0, len(line), 0)]

    def patch(self, start, end, subst):
        mi = iter(self.mapping)
        pi = iter(self.pieces)

        new_mappings = []
        new_pieces = []

        for m in mi:
            if m[1] <= start:
                new_mappings.append(m)
                new_pieces.append(next(pi))

        if m[0] == start:
            pass
        else:
            pass

        """
        mi = iter(self.mapping)

        new_mappings = []

        for first_mapping in mi:
            if first_mapping[1] > start:
                break
            new_mappings.append(first_mapping)
        else:
            return

        if end < first_mapping[0]:
            for last_mapping in mi:
                if end <= last_mapping[0]:
                    break
                new_mappings.append(last_mapping)
        else:
            last_mapping = first_mapping

        ps = self.pieces
        self.pieces = \
            ps[:first_mapping[2]] + [str(substr)] + ps[last_mapping[2]:]

        new_mapping = (first_mapping[0], last_mapping[1], first_mapping[2])

        new_mappings.append(new_mapping)
        for idx, m in enumerate(mi, start = new_mapping[2] + 1):
            new_mappings.append((m[0], m[1], idx))
        """

        print("123")

    def __str__(self):
        return "".join(self.pieces)

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

    args = ap.parse_args()

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
(?P<prefix>< *a +name *= *)\
(?P<quote>["'])\
(?P<name>.*?)\
(?P=quote)\
(?P<infix> *>[^\$<]*)\
(?P<substitution>\$?)\
(?P<suffix>[^<]*< */ *a *>)\
"""
    )

    reference = compile("""\
(?P<prefix>\[)\
(?P<substitution>\$?)\
(?P<infix>]\(#)\
(?P<name>[^\)]+)\
(?P<suffix>\))\
"""
    )

    anchors = {}
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
                    + m.group("prefix") + "|"
                    + m.group("quote") + "|"
                    + m.group("name") + "|"
                    + m.group("quote") + "|"
                    + m.group("infix") + "|"
                    + m.group("substitution") + "|"
                    + m.group("suffix")
                )
                continue

            m = reference.search(l, col)
            if m is not None:
                start, col = m.regs[0]

                references.append(RefInfo(row, start, col, m))

                log(str(row) + "." + str(start) + " reference : "
                    + m.group("prefix") + "|"
                    + m.group("substitution") + "|"
                    + m.group("infix") + "|"
                    + m.group("name") + "|"
                    + m.group("suffix")
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
                log("no anchors found for relative reference " + ref.id)
            elif la > 1:
                log("too many (%u) anchors found for relative reference %s" % (
                    la, ref.id
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
                log("no anchors found for reference " + ref.id)
            elif la > 1:
                log("too many (%u) anchors found for reference %s" % (
                    la, ref.id
                ))

            a = ref.anchors[0]
            if a.substitution is None:
                a.substitution = str(next(source_num_gen))
            ref.substitution = a.substitution
        elif ref.type == "pic":
            pass
        elif ref.type is not None:
            log("unknown reference type %s at %u.%u" % (
                ref.type, ref.row, ref.start
            ))

    picture_num_gen = count(1)
    for a in anchors.values():
        if a.type == "rel":
            pass
        elif a.type == "ref":
            pass
        elif a.type == "pic":
            a.substitution = str(next(picture_num_gen))
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
            if not m.group("substitution"):
                continue

            line = line[:m.start("substitution")] \
                    + pi.substitution \
                    + line[m.end("substitution"):]

        lines[row] = line

    for l in lines:
        out_file.write(str(l))

    out_file.close()
