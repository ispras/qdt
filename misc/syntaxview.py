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

    def __init__(self, stree, suffix):
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

        self.source = origin
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
    sw = SyntaxView(root)
    sw.pack(fill = BOTH, expand = True, side = LEFT)

    resview = SyntaxView(root)
    resview.pack(fill = BOTH, expand = True, side = RIGHT)

    for fn in args.files:
        try:
            with open(fn, "r") as f:
                content = f.read()
        except:
            print_exc()
            continue

        res = do_stage(content, backslash_lexer, backslash_parser)

        sw.append_syntax_tree(res, backslash_lexer.ignored)

        st = Stage(res, backslash_lexer.ignored)
        resview.insert(END, st.result)

        # Token highlighting

        rtext = resview.text
        otext = sw.text

        rtext.tag_configure("hl", background = "yellow")
        otext.tag_configure("hl", background = "yellow")

        res_hls = []
        origin_hls = []

        def on_b1(e):
            while res_hls:
                rtext.tag_remove("hl", *res_hls.pop())
            while origin_hls:
                otext.tag_remove("hl", *origin_hls.pop())

            # line & column under mouse cursor
            line, col = rtext.index("@%d,%d" % (e.x, e.y)).split(".")
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

            i1 = "%d.%d" % (line_n, i1_col)
            i2 = "%d.%d" % (line_n, i2_col)

            hl = (i1, i2)
            res_hls.append(hl)

            rtext.tag_add("hl", *hl)

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
            origin_hls.append(ohl)
            otext.tag_add("hl", *ohl)

            otext.see(oi1)

        rtext.bind("<Button-1>", on_b1, "+")

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
