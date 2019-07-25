from six.moves.tkinter import (
    END,
    LEFT,
    RIGHT,
    BOTH,
    Tk
)
from widgets import (
    SyntaxView
)
from common import (
    bidict,
    pypath,
    join_tokens,
    bind,
    Persistent
)
from argparse import (
    ArgumentParser
)
from source import (
    backslash_lexer,
    backslash_parser,
    ctags_lexer,
    ctags_parser
)
from traceback import (
    print_exc
)
from common import (
    intervalmap
)
with pypath("..ply"):
    from ply.helpers import (
        iter_tokens
    )


class Stage(object):

    def __init__(self, stree, suffix, prev_stage = None):
        self.prev_stage = prev_stage

        result = ""
        origin = ""
        prev = 0

        # result offset to token
        resmap = intervalmap()

        for tok in iter_tokens(stree):
            origin += tok.prefix or ""

            val = tok.value

            result += val
            origin += val

            cur = prev + len(val)

            resmap[prev:cur] = tok
            prev = cur

        origin += suffix

        self.origin = origin
        self.result = result

        self.resmap = resmap

        # result line index to offset of first line's character in the result
        linemap = []
        off = 0
        for line in result.splitlines(True):
            linemap.append(off)
            off += len(line)

        self.linemap = linemap

        # origin offset to origin line index
        originmap = intervalmap()
        prev = 0
        for idx, line in enumerate(origin.splitlines(True)):
            cur = prev + len(line)
            originmap[prev:cur] = idx
            prev = cur

        self.orgmap = originmap


def do_stage(content, lexer, parser, debug = False):
    parse = bind(parser.parse, lexer = lexer)

    lexer.lineno = 1
    lexer.columnno = 1

    try:
        res = parse(content)
    except:
        if debug:
            raise # it's already debug launch
        do_stage(content, lexer, parser, debug = True)
    else:
        if debug:
            raise AssertionError(
                "The previous exception must be raised again by parse!"
            )

    return res


def main():
    ap = ArgumentParser(
        "File syntax viewer"
    )
    ap.add_argument("files", nargs = "*")

    args = ap.parse_args()

    root = Tk()

    for fn in args.files:
        try:
            with open(fn, "r") as f:
                content = f.read()
        except:
            print_exc()
            continue

        st2sv = bidict()
        sv2st = st2sv.mirror

        st = None

        for lexer, parser in [
            (backslash_lexer, backslash_parser),
        ]:
            res = do_stage(content, lexer, parser)

            stage_view = SyntaxView(root)
            stage_view.pack(fill = BOTH, expand = True, side = LEFT)
            stage_view.append_syntax_tree(res, lexer.ignored)

            st2sv[st] = stage_view

            st = Stage(res, lexer.ignored, st)
            content = st.result

        final_view = SyntaxView(root)
        final_view.pack(fill = BOTH, expand = True, side = LEFT)
        final_view.insert(END, content)
        st2sv[st] = final_view

        # Token highlighting
        def on_b1(e):
            # remove previous highlighting
            for sv in sv2st:
                text = sv.text
                current = iter(text.tag_ranges("hl"))
                while True:
                    try:
                        left = next(current)
                    except StopIteration:
                        break
                    right = next(current)
                    text.tag_remove("hl", left, right)

            sv = e.widget.master
            st = sv2st[sv]

            if st is None:
                # left most view
                return

            text = sv.text

            # line & column under mouse cursor
            line, col = sv.index_tuple("@%d,%d" % (e.x, e.y))
            try:
                line_n = int(line)
                col = int(col)
            except ValueError:
                return

            # highlight the token in result text
            line_start = st.linemap[line_n - 1]
            off = line_start + col
            l, r = st.resmap.interval(off)

            # indices of the token value in result text for adding the
            # highlighting tag
            i1_col = l - line_start
            i2_col = r - line_start

            # syntax view replaces each tab with 4 symbols
            i2_col += st.origin[l:r].count('\t') * 3

            i1 = "%d.%d" % (line_n, i1_col)
            i2 = "%d.%d" % (line_n, i2_col)

            hl = (i1, i2)

            text.tag_add("hl", *hl)

            # highlight the token in original text
            tok = st.resmap[off]
            origin_off = tok.lexpos
            origin_line_n = st.orgmap[origin_off] + 1
            ol, _ = st.orgmap.interval(origin_off)

            oi1_col = origin_off - ol
            oi2_col = oi1_col + (r - l) # length of token value

            oi1 = "%d.%d" % (origin_line_n, oi1_col)
            oi2 = "%d.%d" % (origin_line_n, oi2_col)

            ohl = (oi1, oi2)

            otext = st2sv[st.prev_stage].text
            otext.tag_add("hl", *ohl)
            otext.see(oi1)

        for sv in sv2st:
            sv.text.tag_configure("hl", background = "yellow")
            sv.text.bind("<Button-1>", on_b1, "+")

        break # only one file for now

    with Persistent(".syntax-view-settings.py",
        geometry = (650, 900)
    ) as cfg:

        def set_geom():
            root.geometry("%dx%d" % cfg.geometry)

        root.after(10, set_geom)

        def on_destroy_root(_):
            # ignore screen offset
            cfg.geometry = root.winfo_width(), root.winfo_height()

        root.bind("<Destroy>", on_destroy_root, "+")

        root.mainloop()


if __name__ == "__main__":
    main()
