#!/usr/bin/python
# coding=utf-8
# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :

DEBUG = 1

from argparse import \
    ArgumentParser

import sys

from re import \
    UNICODE, \
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
            self.type, self.tag = self.name.split(b".")
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

ABOVE = u"выше".encode("utf-8")
BELOW = u"ниже".encode("utf-8")
DOUBLE_QUOTE_LEFT = u"«".encode("utf-8")
DOUBLE_QUOTE_RIGHT = u"»".encode("utf-8")

if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("in_file_name", nargs = "?", metavar = "in-file-name")
    ap.add_argument("--out-file-name", "-o", nargs = "?")
    ap.add_argument("--ispras", action = 'store_true')
    ap.add_argument("--refs",
        nargs = "?",
        metavar = "index",
        help = "Maintain references enumeration in the index file."
    )
    ap.add_argument("--caption-number-prefix",
        action = "store_true",
        help = "Reset table & picture enumeration when 1st level caption"
            "number increases. Add a prefix with 1st level caption number to"
            "both table & picture number."
    )

    args = ap.parse_args()

    # load known reference numbers from the file
    try:
        refs_file = args.refs
        with open(refs_file, "r") as f:
            refs_data = f.read()
    except:
        refs_data = "{}"
    refs = eval(refs_data)

    ispras = args.ispras
    cnp = args.caption_number_prefix

    enum_captions = ispras or cnp

    try:
        in_file_name = args.in_file_name
    except:
        in_file = sys.stdin
    else:
        in_file = open(in_file_name, "rb")

    out_file_name = args.out_file_name
    if out_file_name is None:
        sys.stderr.write("version: " + str(sys.version_info) + "\n")
        if sys.version_info[0] == 3:
            class RawOut(tuple):
                def write(self, raw):
                    self[0].write(raw.decode("utf-8"))
                def close(self):
                    self[0].close()

            out_file = RawOut((sys.stdout,))
        else:
            out_file = sys.stdout
        log_file = sys.stderr
    else:
        out_file = open(out_file_name, "wb")
        log_file = sys.stdout

    def log(msg):
        log_file.write(msg + "\n")

    anchor = compile(b"""\
\[?\
(?P<substitution2>\$?)\
\]?\
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

    reference = compile(b"""\
(?P<prefix>\[)\
(?P<substitution1>\$?)\
(?P<infix>]\(#)\
(?P<name>[^\)]+)\
(?P<suffix>\))\
"""
    )

    # Auto add a non-breaking space before each long dash
    dash = compile(b"\s---")
    dash_nbs = u"\u00a0---".encode("utf-8")

    anchors = OrderedDict()
    references = []
    lines = []

    code_block = False

    # automatic caption enumeration
    if enum_captions:
        levels = [0]

    row = -1;

    picture_num_gen = count(1)
    table_num_gen = count(1)

    # tap_pfx : tABLE aND pICTURE pREfIx
    if cnp:
        tap_pfx = b"1."
    else:
        tap_pfx = b""

    first_non_empty_line = True

    while True:
        l = in_file.readline()
        if not l: # empty string is EOF
            break

        row += 1

        if l.startswith(b"```"):
            code_block = not code_block
            lines.append(l)
            continue

        if code_block:
            lines.append(l)
            continue

        # Avoid matching YAML header with long dash pattern
        if not first_non_empty_line:
            if l.startswith(b"---"):
                # join "---" with previous non-empty line
                while lines[-1] == b"\n":
                    row -= 1
                    lines.pop()

                # strip '\n' and inset ' ' match `dash` regexp.
                l = lines.pop()[:-1] + b" " + l
                row -= 1

            l = dash.sub(dash_nbs, l)

        if first_non_empty_line and l.strip():
            first_non_empty_line = False

        lines.append(l)

        if enum_captions and l[0:1] == b"#":
            if ispras:
                # Insert empty line before headers of level 1+.
                # Note that 1st level in this preprocessor corresponds to
                # 2nd heading level in terms of
                # Template_for_Proceedings_of_ISP_RAS.dotm
                lines.insert(row, b"\n")
                lines.insert(row, b"<br>\n")
                row += 2

            # Both anchors & references can contain `$`.
            # Hecnce, `$` used for caption enumeration must be processed
            # independently.
            macro_parts = l.split(b"<")

            parts = macro_parts[0].split(b"$")

            if len(parts) > 1:
                current = len(levels)

                line_level = len(parts) - 2

                for tmp in range(current, line_level + 1):
                    levels.append(0)

                for tmp in range(line_level + 1, current):
                    levels.pop()

                levels[line_level] += 1

                if cnp:
                    # reset picture and table enumeration
                    if line_level == 0: # 1st level actually
                        picture_num_gen = count(1)
                        table_num_gen = count(1)

                        tap_pfx = b"%d." % levels[line_level]

                l = b""
                for p, lvl in zip(parts, levels):
                    l += p + b"%d" % lvl

                l += parts[-1]

                # do not forget the tail
                if len(macro_parts) > 1:
                    l += b"<" + b"<".join(macro_parts[1:])

                # line was changed, overwrite
                lines[row] = l

        col = 0
        while True:
            m = anchor.search(l, col)

            if m is not None:
                start, col = m.regs[0]

                a = AnchorInfo(row, start, col, m)

                anchors[m.group("name")] = a

                if DEBUG < 1:
                    log(str(row) + "." + str(start) + " anchor : "
                        + str(m.groupdict())
                    )

                if a.type == b"rel":
                    pass
                elif a.type == b"ref":
                    pass
                # picture and table enumeration
                elif a.type == b"pic":
                    a.substitution = tap_pfx + b"%d" % next(picture_num_gen)
                elif a.type == b"tbl":
                    a.substitution = tap_pfx +  b"%d" % next(table_num_gen)
                elif a.type is not None:
                    log("unknown anchor type %s at %u.%u" % (
                        a.type, a.row, a.start
                    ))

                continue

            m = reference.search(l, col)
            if m is not None:
                start, col = m.regs[0]

                references.append(RefInfo(row, start, col, m))

                if DEBUG < 1:
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
        if ref.type == b"rel":
            if la == 0:
                log("no anchors found for relative reference %s" % ref.tag)
                continue
            elif la > 1:
                log("too many (%u) anchors found for relative reference %s" % (
                    la, ref.tag
                ))

            a = ref.anchors[0]
            if a.row == ref.row:
                if a.start < ref.start:
                    ref.substitution = ABOVE
            elif a.row < ref.row:
                ref.substitution = ABOVE
            else:
                ref.substitution = BELOW
        elif ref.type == b"ref":
            if la == 0:
                log("no anchors found for reference %s" % ref.tag)
                continue
            elif la > 1:
                log("too many (%u) anchors found for reference %s" % (
                    la, ref.tag
                ))

            a = ref.anchors[0]
            if a.substitution is None:
                a.substitution = b"%d" % next(source_num_gen)
            ref.substitution = a.substitution
        elif ref.type == b"pic":
            pass
        elif ref.type == b"tbl":
            pass
        elif ref.type is not None:
            log("unknown reference type %s at %u.%u" % (
                ref.type, ref.row, ref.start
            ))

    for a in anchors.values():
        # propagate both picture and table numbers to its references
        if a.type == b"pic":
            for ref in a.references:
                ref.substitution = a.substitution
        elif a.type == b"tbl":
            for ref in a.references:
                ref.substitution = a.substitution
        elif a.type == b"ref":
            if a.substitution is None:
                # The reference is not referenced by anything in that file.
                # Try to find its number in the index file.
                a.substitution = refs.get(a.tag, None)

    # patch lines
    code_block = False

    for row, line in enumerate(list(lines)):
        if line.startswith(b"```"):
            code_block = not code_block
            continue

        if code_block:
            continue

        pis = [
            pi for pi in references + list(anchors.values()) if pi.row == row
        ]

        if not pis:
            continue

        pis = sorted(pis, key = lambda pi :-pi.start)

        for pi in pis:
            if pi.type == b"pic":
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
                    if ispras and not isinstance(pi, AnchorInfo):
                        new_line = (line[:m.start("prefix")]
                            + pi.substitution
                            + line[m.end("suffix"):]
                        )
                    else:
                        new_line = (line[:m.start(subst)]
                            + pi.substitution
                            + line[m.end(subst):]
                        )
                    # note that line could be changed multiple times
                    line = new_line

        lines[row] = line

    # sort sources by reference order
    ref_anchors = [ a for a in anchors.values() if \
        a.type == b"ref" and a.substitution is not None
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

    if ispras:
        code_block = False

        for idx, l in enumerate(list(lines)):
            code = False
            tag = False
            new_word = True

            if l.startswith(b"```"):
                code_block = not code_block
                continue

            if code_block:
                continue

            new_line = b""
            for i in range(len(l)):
                c = l[i:i+1]
                if c == b"`":
                    code = not code
                elif not code:
                    if c == b"<":
                        tag = True
                    elif c == b">":
                        tag = False
                if (not (code or tag)) and c == b'"':
                    if new_word:
                        c = DOUBLE_QUOTE_LEFT
                    else:
                        c = DOUBLE_QUOTE_RIGHT

                new_word = (c == b" ")

                new_line = new_line + c

            l = new_line

            lines[idx] = l


    for l in lines:
        out_file.write(l)

    out_file.close()

    # Update references index file with only references used in just
    # preprocessed file.
    if refs_file:
        refs.update((a.tag, a.substitution) for a in ref_anchors)
        with open(refs_file, "w+") as f:
            f.write(repr(refs))
