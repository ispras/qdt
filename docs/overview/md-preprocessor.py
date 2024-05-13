#!/usr/bin/env python3
# coding=utf-8
# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8 :

DEBUG = 1

from argparse import \
    ArgumentParser

from sys import \
    stderr, \
    stdin, \
    stdout, \
    version_info

from re import \
    MULTILINE, \
    UNICODE, \
    compile

from itertools import \
    chain, \
    count

from collections import \
    defaultdict, \
    OrderedDict

from os import \
    getcwd

from os.path import \
    dirname, \
    exists, \
    join, \
    splitext


def err(fmt, *args):
    stderr.write(fmt % args + "\n")
    stderr.flush()


TOPLEVELONLY_TAG = b"#toplevelonly"
ABBREV_TAG = b"#abbreviations"
TAIL_TAG = b"#tail"

tags = set((b"#" + t) for t in [
    b"codetable"
])

TAGS = (
    ABBREV_TAG[1:],
    TAIL_TAG[1:],
    TOPLEVELONLY_TAG[1:],
    b"codetable",
)

ABOVE = u"выше".encode("utf-8")
BELOW = u"ниже".encode("utf-8")
DOUBLE_QUOTE_LEFT = u"«".encode("utf-8")
DOUBLE_QUOTE_RIGHT = u"»".encode("utf-8")

# Auto add a non-breaking space before each long dash
dash = compile(b"\s---")
dash_nbs = u"\u00a0\u2014".encode("utf-8")

spec_chars = u'~`@№#$%^&*_=+[{]}\\|/\'<>'

re_from = compile(b"\
\s*#+\s*from\s*\
['\"](?P<file>[^'\"]*)['\"]\
\s*include\s*\
(?P<flags>[-]*)\s*\
['\"](?P<title>[^'\"]*)['\"]\
(\s*shift\s*\
(?P<shift>-?[1-9][0-9]*)\
)?\
")

NUM_PLACE = b"([$]|\d+)"

# https://www.rfc-editor.org/rfc/rfc3986
re_uri = compile(b"^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?")

re_title = compile(b"\
\s*\
(?P<level_prefix>#+)\
\s*\
(?P<number>("
    + NUM_PLACE
    + b"[.]("
    + NUM_PLACE
    + b"([.]"
    + NUM_PLACE
    + b")*)?)?)\
\s*\
(?P<title>(.*?(?=(\s*{#(?P<id>.+)})|$))?)\
\s*\
")

re_hash_ref = compile(b"\
[[]\s*\
(?P<text>[^[]*?(?=]))\
]\s*[(]\s*#\
(?P<id>.*?(?=[)]))\
[)]")

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

# Note that | is table syntax.
re_code_block = compile(b"[|]?\s*```.*")
re_strict_code_block = compile(b"```.*")

re_include = compile(b"#\s*include[\s]+(?P<file_name>.+)")


re_md_pic = compile(b"!\[(?P<title>[^\]]*)\]\s*\((?P<file_name>[^)]*)\)")

re_gost_pic_title = compile("Рисунок.*")

re_blank = compile(b"[ \t\n\r]+")
re_blank_line = compile(b"[ \t\n\r]+$", MULTILINE)

# Some characters cannot be in an abbreviation.
abbrev_forbidden = set(u"=\"'.()")

shortcuts = [
    [u"(?!\\w)(т\\.к\\.)(?!\\w)", (u"так как",)],
    [u"(?!\\w)(Т\\.к\\.)(?!\\w)", (u"Так как",)],
    [u"(?!\\w)(т\\.о\\.)(?!\\w)", (u"таким образом",)],
    [u"(?!\\w)(Т\\.о\\.)(?!\\w)", (u"Таким образом",)],
    [u"(?!\\w)(т\\.е\\.)(?!\\w)", (u"то есть",)],
    [u"(?!\\w)(Т\\.е\\.)(?!\\w)", (u"То есть",)],
]


def is_local_path(path):
    m = re_uri.match(path)
    if not m:
        return bool(path)
    if m.group(1):  # e.g., http:
        return False
    if m.group(3):  # e.g., //example.org
        return False
    if m.group(6):  # e.g. ?query...
        return False
    if m.group(8):  # e.g. #fragment
        return False
    return bool(m.group(5))  # path


used_files = set()

auto_add_numbers = False

class Block(list):

    # empty by default
    tags = tuple()

    # no generic regular expression for arbitrary block
    re = None

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)

        self._update_by_re()

    def __iter_lines__(self):
        for i in self:
            if isinstance(i, Block):
                for ii in i.__iter_lines__():
                    yield ii
            else:
                yield i

    def __iter_source__(self):
        for i in chain(self.tags, self):
            if isinstance(i, Block):
                for ii in i.__iter_source__():
                    yield ii
            else:
                yield i

    def __str__(self):
        return type(self).__name__

    def __bytes__(self):
        return b"".join(self.__iter_lines__())

    @property
    def utf8(self):
        return bytes(self).decode("utf-8")

    def iter_depth_first(self):
        for b in self:
            yield b
            if isinstance(b, Block):
                for bb in b.iter_depth_first():
                    yield bb

    def iter_chapters(self):
        for b in self:
            if isinstance(b, Chapter):
                yield b

    def iter_find_chapter(self, name):
        for b in self.iter_depth_first():
            if not isinstance(b, Chapter):
                continue
            if b.title == name:
                yield b

    def _update_by_re(self):
        re = self.re
        if re is None:
            return

        m = re.match(bytes(self[0]))

        self.__dict__.update(m.groupdict())

    def set_by_re(self, **nv):
        cur = bytes(self[0])
        m = self.re.match(cur)

        patches = reversed(sorted((m.span(n) + (n,) for n in nv)))

        for s, e, n in patches:
            cur = cur[:s] + nv[n] + cur[e:]

        self[0] = cur

        self._update_by_re()


class MDFile(Block): pass

class CodeBlock(Block): pass

class JointLines(Block):

    @property
    def joint(self):
        return b"".join(l.rstrip(b"\\\n\r") for l in self[:-1]) + self[-1]

    def __iter_lines__(self):
        yield self.joint


class YAMLHeader(Block): pass

class Paragraph(Block): pass

class Title(Block):

    re = re_title

    def _update_by_re(self):
        super(Title, self)._update_by_re()
        self.level = len(self.level_prefix) - 1

    def shift(self, delta):
        level = self.level
        new_level = level + delta
        if new_level < 0:
            err("%s: level is %s, can't shift %s",
                self.title.decode("utf-8"),
                level,
                delta
            )
            return

        number = self.number

        if delta != 0:
            d = dict(
                level_prefix = b"#" * (new_level + 1)
            )

            if number:
                number = b".".join([b"$"] * (new_level + 1))
                if new_level == 0:
                    number += b"."
                d["number"] = number

            self.set_by_re(**d)


def format_number(n):
    ret = b".".join(map(b"%d".__mod__, n))
    if len(n) == 1:
        ret += b"."
    return ret


class Chapter(Block):

    @property
    def title_block(self):
        title = self[0]
        assert isinstance(title, Title)
        return title

    @property
    def enumerated(self):
        return bool(self.title_block.number)

    @property
    def number(self):
        tb = self.title_block
        if not tb.number:
            return None
        if b"$" in tb.number and hasattr(self, "auto_number"):
            return format_number(self.auto_number)
        else:
            return tb.number

    def __str__(self):
        return self.title.decode("utf-8")

    @property
    def title(self):
        return self.title_block.title

    @property
    def id(self):
        return self.title_block.id


class Tags(Block): pass

class Inclusion(Block): pass

class ChapterInclusion(Block):

    re = re_from

    def _update_by_re(self):
        super(ChapterInclusion, self)._update_by_re()
        shift = self.shift
        self.shift = 0 if shift is None else int(shift)

class Picture(Block):

    re = re_md_pic

    def set_file(self, file):
        return self.set_by_re(file_name = file)

    def set_title(self, title):
        return self.set_by_re(title = title)


def iter_queue_children(b):
    for i, c in enumerate(b):
        yield b, i, c


def preprocess(md):
    # chapter enumeration and id dict creation
    id2ch = {}
    num = []
    q = list(md.iter_chapters())

    while q:
        c = q.pop(0)

        if c.id:
            id2ch[c.id] = c

        l = c.title_block.level

        # auto add numbers to all inner chapters
        if auto_add_numbers and not c.enumerated and l > 0:
            c.title_block.set_by_re(
                number = b".".join([b"$"] * (l + 1)) + b" "
            )

        if c.enumerated:
            while len(num) < l:
                num.append(1)
            if len(num) < l + 1:
                num.append(1)
            else:
                num[l] += 1
                del num[l + 1:]

            c.auto_number = tuple(num)

        q = list(c.iter_chapters()) + q

    q = list(iter_queue_children(md))
    while q:
        p, i, cur = q.pop(0)

        if isinstance(cur, bytes):
            is_line = True
            l = cur
        elif isinstance(cur, JointLines):
            is_line = True
            l = bytes(cur)
        else:
            is_line = False

        if is_line:
            for m in re_hash_ref.finditer(l):
                ch_id = m.group("id")
                if ch_id in id2ch:
                    ch = id2ch[ch_id]
                    if ch.enumerated:
                        s, e = m.span("text")
                        l = l[:s] + ch.number.rstrip(b".") + l[e:]
                        p[i] = cur = l
                else:
                    if DEBUG < 1:
                        log("no chapter with id %s" % ch_id)

        else:
            assert isinstance(cur, Block) and not isinstance(cur, JointLines)
            q.extend(iter_queue_children(cur))

    return md


def p_file(in_file, file_name):
    liter = iter(in_file.readlines())
    md = MDFile(i_tree(liter))
    p_from_include(md, file_name)
    return md


def p_from_include(parent, file_name):
    for p, i, cur in reversed(list(iter_queue_children(parent))):
        assert p is parent
        if isinstance(cur, ChapterInclusion):
            parent[i:i + 1] = list(i_from_include(cur, file_name))
        elif isinstance(cur, Picture):
            if not re_gost_pic_title.match(cur.title.decode("utf-8")):
                # Auto ID is based on original file path (path adjustment
                # by inclusion does not
                # affect it because auto ID can be assumed by writer
                # and used in referecnes in the included document).
                # TODO: This approach can result in ID conflicts.
                #       Analyze entire included Markdown file to find all
                #       references to IDs of pictures and adjusts IDs
                #       according to actual directory of included file.
                auto_id = id_from_file_path(cur.file_name.decode("utf-8"))
                cur.set_title(
                    (
                        "Figure <a name=\"pic.%s\">$</a> --- " % auto_id
                    ).encode("utf-8")
                    + cur.title
                )
        elif isinstance(cur, Block):
            p_from_include(cur, file_name)


def i_from_include(cur, file_name):
    file_dir = dirname(file_name)
    file = cur.file.decode("utf-8")
    actual_file = join(file_dir, file)
    flags = cur.flags
    title = cur.title
    shift = cur.shift

    if DEBUG < 0:
        log("from '%s' ('%s') include %s'%s' shift %s" % (
            file, actual_file,
            flags.decode("utf-8"),
            title.decode("utf-8"),
            shift
        ))

    used_files.add(actual_file)

    if exists(actual_file):
        imd = p_file(open(actual_file, "rb"), actual_file)
        actual_dir = dirname(actual_file)

        for chapter in imd.iter_find_chapter(title):
            if b'-' in flags:
                # remove title and convert
                chapter.pop(0)

            # - fixup picture paths
            # - apply shift to titles
            for b in chapter.iter_depth_first():
                if isinstance(b, Picture):
                    raw_pic_file = b.file_name
                    pic_file = raw_pic_file.decode("utf-8")
                    # 1. a picture could be a URI pointing to network
                    # 2. a picture could be generated, not yet exists
                    if is_local_path(raw_pic_file):
                        actual_pic_file = join(actual_dir, pic_file)
                        b.set_file(actual_pic_file.encode("utf-8"))
                    else:
                        log("not a local path: %s" % pic_file)

                if isinstance(b, Title):
                    b.shift(shift)

            if b'-' in flags:
                for b in chapter:
                    yield b
            else:
                yield chapter
            break
        else:
            err("chapter '%s' is not found", title.decode("utf-8"))
    else:
        err("file '%s' is not found", actual_file)


def is_line_joining(l):
    stripped = l.rstrip(b"\n\r")
    return stripped[-1:] == b'\\' and stripped[-2:] != b"\\\\"


def is_YAML_header_begin(l):
    return l.rstrip() == b"---"


def is_YAML_header_end(l):
    return l.rstrip() == b"..."


def is_title(l):
    return l.lstrip()[:1] == b'#'


def i_tree(i):
    stack = []
    for b in i_tagged_blocks(i):

        if isinstance(b, YAMLHeader):
            if stack:
                yield stack[0]
                del stack[:]
            yield b
            continue

        if isinstance(b, Title):
            level = b.level

            c = Chapter([b])

            if level == 0:
                if stack:
                    yield stack[0]
                    del stack[:]
            else:
                parent = level - 1

                if not stack:
                    stack.append(Chapter())

                for __ in range(len(stack), level):
                    tmp_c = Chapter()
                    stack[-1].append(tmp_c)
                    stack.append(tmp_c)

                del stack[level:]

                stack[-1].append(c)

            stack.append(c)
            continue

        if stack:
            stack[-1].append(b)
        else:
            yield b

    if stack:
        yield stack[0]
        # del stack[:]  # is not required here


wrap_all_code_blocks = True

def id_from_file_path(p):
    return "".join(iter_id_from_file_path(p))

def iter_id_from_file_path(p):
    for c in splitext(p)[0]:
        if not c.isalnum():
            c = "-"
        yield c

def i_tagged_blocks(i):
    tags = Tags()

    for b in i_middle_blocks(i):
        if isinstance(b, Title):
            if b.title in TAGS:
                tags.append(b)
                continue

        if wrap_all_code_blocks and isinstance(b, CodeBlock):
            if tags:
                for t in tags:
                    if t.title == b"codetable":
                        wrap_table = False  # already
                        break
                else:
                    wrap_table = True
            else:
                wrap_table = True

            if wrap_table:
                tags.append(Title([b"#codetable\n"]))

        if tags:
            b.tags = tags
            tags = Tags()

        yield b

    if tags:
        yield tags


def i_middle_blocks(i):
    p = Paragraph()

    for b in i_low_blocks(i):
        if isinstance(b, CodeBlock):
            if p:
                yield p
                p = Paragraph()

            yield b
            continue

        l = bytes(b)

        if is_YAML_header_begin(l):
            if p:
                yield p
                p = Paragraph()

            yield YAMLHeader(i_yaml_header(b, i))
            continue

        if re_include.match(l):
            yield Inclusion([b])
            continue

        if re_from.match(l):
            yield ChapterInclusion([b])
            continue

        if re_md_pic.match(l):
            yield Picture([b])
            continue

        if is_title(l):
            if p:
                yield p
                p = Paragraph()

            yield Title([b])
            continue

        p.append(b)

        if not l.strip():
            yield p
            p = Paragraph()

    if p:
        yield p


def i_low_blocks(i):
    for l in i:
        if re_strict_code_block.match(l):
            yield CodeBlock(i_code_block(l, i))
            continue

        if is_line_joining(l):
            yield JointLines(i_joint_lines(l, i))
            continue

        yield l


def i_code_block(first, i):
    yield first
    for l in i:
        yield l
        if re_strict_code_block.match(l):
            break


def i_joint_lines(f, i):
    yield f
    for l in i:
        yield l
        if not is_line_joining(l):
            break

def i_yaml_header(f, i):
    yield f
    for l in i:
        if is_line_joining(l):
            yield JointLines(i_joint_lines(l, i))
            continue

        yield l
        if is_YAML_header_end(l):
            break


class PosInfo(object):
    def __init__(self, row, start, end, m):
        self.row, self.start, self.end, self.m = row, start, end, m

class PatchInfo(PosInfo):
    def __init__(self, *args):
        super(PatchInfo, self).__init__(*args)

        self.name = self.m.group("name")
        try:
            self.type, self.tag = self.name.split(b".", 1)
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


def wrap_code(lines):
    decoded = list(l.decode("utf-8") for l in lines)
    max_len = max(len(l) for l in decoded)

    out_decoded = [
        "+"
        + "-" * (max_len - 1) # there is \n at and of each line
        + "+\n"
    ]
    for l in decoded:
        out_decoded.append("|" + l[:-1] + " " * (max_len - len(l)) + "|\n")

    out_decoded.append(out_decoded[0])
    out = list(l.encode("utf-8") for l in out_decoded)
    return out


def iter_abbrevs(line):
    "It's a heuristic search for abbreviations."

    for raw_full_w in re_blank.split(line.strip()):
        # Check if `w`ord is an abbreviation. This is a heuristic approach,

        full_w = raw_full_w.decode("utf-8")

        w = u""
        word_started = False
        last_word_char = 0

        for i, c in enumerate(full_w):
            if word_started:
                if c.isalpha() or c.isdigit():
                    last_word_char = len(w)

                w += c

            elif c.isalpha():
                last_word_char = 0
                w += c
                word_started = True

        if not word_started:
            # special symbols only
            continue

        w = w[:last_word_char + 1]

        if len(w) < 2:
            # empty or one char word is not an abbreviation
            continue

        if len(w) > 10:
            # An abbreviation cannot be too long.
            continue

        lower = 0
        upper = 0
        forbidden_char = False

        for c in w:
            if c in abbrev_forbidden:
                forbidden_char = True
                break

            if c.islower():
                lower += 1
            elif c.isupper():
                upper += 1

        if forbidden_char:
            continue

        alpha = lower + upper
        if alpha == 0:
            # No alphabet symbols
            continue

        nonalpha = len(w) - alpha
        if nonalpha > 1 and nonalpha / alpha > 0.5:
            # Too many special symbols
            continue

        if upper <= lower:
            # A name, regular word or composite word
            continue

        yield w


replacements = []

for sc, reps in shortcuts:
    enc_reps = tuple(r.encode("utf-8") for r in reps)

    def _replace(line,
        __re_sc = compile(b".*" + sc.encode("utf-8") + b".*"),
        __replacements = enc_reps
    ):
        return do_replace(line, __re_sc, __replacements)
    replacements.append(_replace)

def do_replace(line, re, reps):
    mi = re.match(line)
    if not mi:
        return line

    groups = list(
        (mi.start(g + 1), mi.end(g + 1), g) for g in range(mi.lastindex)
    )
    groups = list(reversed(sorted(groups)))

    for s, e, g in groups:
        line = line[:s] + reps[g] + line[e:]

    return line


def iter_read_lines(in_file):
    while True:
        l = in_file.readline()
        if not l: # empty string is EOF
            break
        yield l


def iter_file_lines(in_file, file_name):
    code_block = False

    md = preprocess(p_file(in_file, file_name))

    line = b""
    for l in md.__iter_source__():
        if re_code_block.match(l):
            code_block = not code_block

            if code_block and line:
                # escaped newline just before code block
                code_block = False

        striped = l.rstrip(b"\n\r")

        # escaping of newline symbol
        if not code_block and len(striped) > 1 and striped[-1:] == b"\\":
            line += striped[:-1]
            continue

        line += l
        if code_block:
            yield line
        else:
            for ll in iter_inclusions(line):
                yield ll
        line = b""

    if line:
        # escaped newline just before end of file
        line += b"\\\n"
        if code_block:
            yield line
        else:
            for ll in iter_inclusions(line):
                yield ll


def iter_inclusions(joined_line):
    mi = re_include.match(joined_line)
    if mi:
        file_name = mi.group("file_name")
        if exists(file_name):
            used_files.add(file_name.decode("utf-8"))
            prefix = dirname(file_name)
            with open(file_name, "rb") as f:
                liter = iter_skip_header(
                    iter_skip_toplevel(
                        iter_file_lines(f, file_name), False
                    )
                )

                for l in liter:
                    pic_mi = re_md_pic.match(l)
                    if pic_mi:
                        # fixup picture paths
                        raw_pic_file = pic_mi.group("file_name")
                        pic_file = raw_pic_file.decode("utf-8")
                        if is_local_path(raw_pic_file):
                            rel_pic_name = join(prefix, raw_pic_file)
                            yield b"![%s](%s)\n" % (
                                pic_mi.group("title"),
                                rel_pic_name,
                            )
                        else:
                            log("not a local path: %s" % pic_file)
                            yield l
                    else:
                        yield l
        else:
            yield joined_line
    else:
        yield joined_line


def iter_skip_header(liter):
    for l in liter:
        if re_blank_line.match(l):
            yield l
            continue

        if l.rstrip() == b"---":
            for l in liter:
                if l.rstrip() == b"...":
                    break
        else:
            yield l
            break

    for l in liter:
        yield l


def iter_skip_toplevel(liter, toplevel):
    if toplevel:
        for l in liter:
            if l.startswith(TOPLEVELONLY_TAG):
                continue
            yield l
    else:
        for l in liter:
            if l.startswith(TOPLEVELONLY_TAG):
                for l in liter:
                    if re_blank_line.match(l):
                        break
                continue
            yield l


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
    ap.add_argument("--gost-quotes",
        action = "store_true",
        help = u'Repalce " with %s and %s according to GOST' % (
            DOUBLE_QUOTE_LEFT.decode("utf-8"),
            DOUBLE_QUOTE_RIGHT.decode("utf-8")
        )
    )
    ap.add_argument("-A", "--print-undef-abbrevs",
        action = "store_true",
        help = u"Heuristically search and print undefined abbreviations."
            u" Note, abbreviations are defined by tag %s" % (
                ABBREV_TAG.decode("utf-8")
            )
    )
    ap.add_argument("-S", "--no-shortcuts",
        action = "store_true",
        help = "Disable shortcuts replacement such that 'т.к.' -> 'так как'",
    )
    ap.add_argument("-not-abbrev",
        nargs = "?",
        help = "File with a black list of words which are not abbreviations."
            " Newline character is separator."
    )
    ap.add_argument("-u", "--used",
        nargs = 1,
        help = "output list of used files to given file in Makefile format."
    )
    ap.add_argument("--svg2png",
        action = "store_true",
        help = "Renames *.svg file names to *.png file names."
            " Use it to generate MS Office compatible files."
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
    gost_quotes = ispras or args.gost_quotes
    print_undef_abbrevs = args.print_undef_abbrevs
    svg2png = args.svg2png

    not_abbrev_file = args.not_abbrev
    not_abbrev = set()
    if not_abbrev_file is not None:
        used_files.add(not_abbrev_file)
        with open(not_abbrev_file, "rb") as f:
            for l in f.read().split(b"\n"):
                abbr = l.decode("utf-8").strip()
                if abbr:
                    not_abbrev.add(abbr)

    try:
        in_file_name = args.in_file_name
    except:
        in_file_name = join(getcwd(), "stdin")
        in_file = stdin
    else:
        used_files.add(in_file_name)
        in_file = open(in_file_name, "rb")

    out_file_name = args.out_file_name
    if out_file_name is None:
        stderr.write("version: " + str(version_info) + "\n")
        if version_info[0] == 3:
            class RawOut(tuple):
                def write(self, raw):
                    self[0].write(raw.decode("utf-8"))
                def close(self):
                    self[0].close()

            out_file = RawOut((stdout,))
        else:
            out_file = stdout
        log_file = stderr
    else:
        log_file = stdout

    def log(msg):
        log_file.write(msg + "\n")

    anchors = OrderedDict()
    references = []

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

    joint_lines = list(
        iter_skip_toplevel(iter_file_lines(in_file, in_file_name), True)
    )
    in_file.close()

    if svg2png:
        lines = []
        line = lines.append

    for l in joint_lines:
        m = re_md_pic.match(l)
        if m:
            raw_pic_file = m.group("file_name")

            if svg2png:
                if raw_pic_file.endswith(b".svg"):
                    new_fn = raw_pic_file[:-4] + b".png"
                elif raw_pic_file.endswith(b".SVG"):
                    new_fn = raw_pic_file[:-4] + b".PNG"
                else:
                    new_fn = raw_pic_file

                if new_fn == raw_pic_file:
                    line(l)
                else:
                    raw_pic_file = new_fn
                    line(b"![%s](%s)\n" % (
                        m.group("title"),
                        new_fn,
                    ))

            if is_local_path(raw_pic_file):
                used_files.add(raw_pic_file.decode("utf-8"))

        elif svg2png:
            line(l)

    if svg2png:
        joint_lines = lines

    used = args.used
    if used:
        if not out_file_name:
            err("-u option requires -o")
            exit(1)

        with open(used[0], "w") as f:
            f.write(out_file_name + ":")
            for fn in sorted(used_files):
                fn = fn.replace(" ", "\\ ")
                f.write(' \\\n  %s' % fn)
            f.write("\n")
        exit(0)

    # Do it after `-u` option checking.
    # Output file should not be truncated if `-u` option is provided.
    if out_file_name is not None:
        out_file = open(out_file_name, "wb")

    # handle abbreviations
    lines = []

    explicit_abbrevs = set()
    first_abbrev = None
    blank_l = None
    abbrs_defs = []

    liter = iter(joint_lines)
    for l in liter:
        if not l.startswith(ABBREV_TAG):
            lines.append(l)
            continue

        if first_abbrev is None:
            first_abbrev = len(lines)

        for l in liter:
            if re_blank_line.match(l):
                break
            abbrs_defs.append(l.decode("utf-8"))

        if blank_l is None:
            blank_l = l # remember to reuse

    if first_abbrev is not None and abbrs_defs:
        defs = set()
        abbrs = defaultdict(dict)
        for ad in abbrs_defs:
            try:
                a, d = ad.split(u"  ", 1)
            except:
                err(u"Malformed abbreviation: %s", ad)
                raise

            abbr = a.strip()
            explicit_abbrevs.add(abbr)

            d = d.strip()
            # merge definitions ignoring case
            abbrs[abbr].setdefault(d.lower(), d)
            defs.add(d)

        # emit them as table

        abbrs_width = max(map(len, abbrs))
        defs_width = max(map(len, defs))

        separ = (
            b"+" +
            b"-" * (2 + abbrs_width) +
            b"+" +
            b"-" * (2 + defs_width) +
            b"+" +
            b"\n"
        )

        line_format = u"| %%-%ds | %%-%ds |\n" % (abbrs_width, defs_width)

        abbr_lines = [separ]

        abbrs_t = tuple(sorted(list(
            (a, tuple(sorted(list(ds.values()))))
                for (a, ds) in abbrs.items()
        )))

        for a, ds in abbrs_t:
            first_a = True
            for d in ds:
                if first_a:
                    first_a = False
                    adl = line_format % (a, d)
                else:
                    # empty line; next abbreviation will be on new line
                    abbr_lines.append(
                        (line_format % (u"", u"")).encode("utf-8")
                    )
                    adl = line_format % (u"", d)
                abbr_lines.append(adl.encode("utf-8"))
            abbr_lines.append(separ)

        abbr_lines.append(blank_l)

        joint_lines = lines[:first_abbrev] + abbr_lines + lines[first_abbrev:]
    else:
        joint_lines = lines

    # simple replacements
    if not args.no_shortcuts:
        lines = []
        for l in joint_lines:
            for r in replacements:
                l = r(l)
            lines.append(l)
        joint_lines = lines

    # handle #tail tag
    lines = []
    liter = iter(joint_lines)
    code_block = False
    tail_block = False

    tail = []

    for l in liter:
        if tail_block:
            tail.append(l)
            if re_blank_line.match(l):
                tail_block = False
        else:
            if re_code_block.match(l):
                code_block = not code_block
                lines.append(l)
                continue

            if code_block:
                lines.append(l)
                continue

            if l.startswith(TAIL_TAG):
                tail_block = True
                continue

            lines.append(l)

    joint_lines = lines + tail

    first_non_empty_line = True
    lines = []
    for l in joint_lines:
        row += 1

        if re_code_block.match(l):
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
            if ispras and l.strip() not in tags:
                # Insert empty line before headers of level 1+.
                # Note that 1st level in this preprocessor corresponds to
                # 2nd heading level in terms of
                # Template_for_Proceedings_of_ISP_RAS.dotm
                # Also note, there are special #tags which are not headers.
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
        elif ref.type == b"cnt":
            # XXX: account anchors within XML comments too
            ref.substitution = b"%d" % len(list(
                a for a in anchors.values() if a.type == ref.tag
            ))
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
        if re_code_block.match(line):
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

    if gost_quotes:
        code_block = False

        priority = {}
        p = [0]

        def prioretize(*chars):
            cur_p = p[0]
            for c in chars:
                assert c not in priority
                priority[c] = cur_p
            p[0] = cur_p + 1


        prioretize(b'\r', b'\n',)
        prioretize(b' ',)
        prioretize(b'\t',)
        prioretize(b'.', b'!', b'?',  b')', b'(',)
        prioretize(b',', b';',)

        prioretize(*(c.encode("utf-8") for c in spec_chars))

        prioretize(b'-',)

        max_prio = p[0]

        balance = 0

        for idx, l in enumerate(list(lines)):
            code = False
            tag = False
            new_word = True

            if re_code_block.match(l):
                code_block = not code_block
                if code_block:
                    balance = 0
                continue

            if code_block:
                continue

            # Конец абзаца сбрасывает баланс кавычек
            if not l.strip():
                balance = 0

            left_prio = -1
            quote = False
            new_line = b""
            for i in range(len(l)):
                c = l[i:i+1]
                if c == b"`":
                    if code:
                        assert not quote, "line: " + l.decode("utf-8")
                        code = False
                    else:
                        if quote:
                            new_line += DOUBLE_QUOTE_LEFT
                            quote = False
                        code = True
                elif c == b"<":
                    if not code:
                        tag = True
                elif c == b">":
                    if not code:
                        tag = False

                if (not (code or tag)) and c == b'"':
                    if quote:
                        new_line += DOUBLE_QUOTE_LEFT + DOUBLE_QUOTE_RIGHT
                        quote = False
                    else:
                        quote = True
                    c = b""
                else:
                    try:
                        prio = priority[c]
                    except KeyError:
                        prio = max_prio

                    if quote:
                        if left_prio < prio:
                            new_line += DOUBLE_QUOTE_LEFT
                            balance += 1
                        elif left_prio > prio:
                            new_line += DOUBLE_QUOTE_RIGHT
                            balance -= 1
                        elif balance <= 0:
                            new_line += DOUBLE_QUOTE_LEFT
                            balance += 1
                        else:
                            new_line += DOUBLE_QUOTE_RIGHT
                            balance -= 1

                        quote = False

                    left_prio = prio
                    new_line = new_line + c

            if quote:
                new_line += DOUBLE_QUOTE_RIGHT
                balance -= 1
                quote = False

            l = new_line

            lines[idx] = l

    new_lines = []
    code_table = False
    for l in lines:
        if l.startswith(b"#codetable"):
            code_table = True
            code = []
            continue

        if code_table:
            if re_code_block.match(l):
                if code:
                    # ending code block
                    code_table = False
                    code.append(l)
                    new_lines.extend(wrap_code(code))
                    continue

        if code_table:
            code.append(l)
        else:
            new_lines.append(l)

    lines = new_lines

    for l in lines:
        out_file.write(l)

    out_file.close()

    # Update references index file with only references used in just
    # preprocessed file.
    if refs_file:
        refs.update((a.tag, a.substitution) for a in ref_anchors)
        with open(refs_file, "w+") as f:
            f.write(repr(refs))

    if print_undef_abbrevs:
        auto_abbrevs = set()
        for l in lines:
            for abbr in iter_abbrevs(l):
                if abbr in not_abbrev:
                    continue
                auto_abbrevs.add(abbr)

        for abbr in sorted(auto_abbrevs - explicit_abbrevs):
            print(abbr)
