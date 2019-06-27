from six.moves.tkinter import (
    BOTH,
    Tk
)
from widgets import (
    SyntaxView
)
from common import (
    join_tokens,
    bind,
    Persistent
)
from argparse import (
    ArgumentParser
)
from source import (
    backslash_lexer,
    backslash_parser
)
from traceback import (
    print_exc
)


lexer = backslash_lexer
parser = backslash_parser
parse = bind(parser.parse, lexer = lexer)


def main():
    ap = ArgumentParser(
        "File syntax viewer"
    )
    ap.add_argument("files", nargs = "*")

    args = ap.parse_args()

    root = Tk()
    sw = SyntaxView(root)
    sw.pack(fill = BOTH, expand = True)

    for fn in args.files:
        try:
            with open(fn, "r") as f:
                content = f.read()

            lexer.lineno = 1
            lexer.columnno = 1

            try:
                res = parse(content)
            except:
                lexer.lineno = 1
                parse(content, debug = True)
                raise AssertionError(
                    "The previous exception must be raised again by parse!"
                )
        except:
            print_exc()
            continue

        sw.append_syntax_tree(res, lexer.ignored)
        print(join_tokens(res))

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
