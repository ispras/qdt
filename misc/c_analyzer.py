from common import (
    pypath,
)
from source import (
    get_cpp_search_paths,
    iter_gcc_defines,
)
from widgets import (
    add_scrollbars_native,
    ExText,
    decorate_ignored,
    GUIText,
    GUITk,
    READONLY,
)

with pypath("..ply"):
    import ply.cpp
    from ply.cpp import (
        Preprocessor,
    )
    from ply.lex import (
        lex,
    )

from argparse import (
    ArgumentParser,
)
from os.path import (
    basename,
    dirname,
)
from six.moves.tkinter import (
    BOTH,
    BOTTOM,
    END,
    Frame,
    LEFT,
    RIGHT,
    TOP,
)

gcc_defines = tuple(iter_gcc_defines())
cpp_search_paths = get_cpp_search_paths()
cpp_lexer = lex(ply.cpp)


tok_id2source = {}

class LexerWrapper():

    def __init__(self, lexer):
        self.source = None
        self.lexer = lexer

    def clone(self):
        ret = LexerWrapper(self.lexer.clone())
        ret.source = self.source
        return ret

    def token(self):
        tok = self.lexer.token()
        tok_id2source[id(tok)] = self.source
        return tok

    def input(self, data):
        self.lexer.input(data)


cpp_lexer_w = LexerWrapper(cpp_lexer)


class CAnalyzerPreprocessor(Preprocessor):

    def parsegen(self, input_, source = None):
        prev_source = self.lexer.source
        self.lexer.source = source
        for t in super(CAnalyzerPreprocessor, self).parsegen(input_,
            source = source,
        ):
            yield t
        self.lexer.source = prev_source


class CAnalyzerTk(GUITk):

    def __init__(self, *a, **kw):
        super(CAnalyzerTk, self).__init__(*a, **kw)

        top = Frame(self)
        top.pack(side = TOP, fill = BOTH, expand = True)

        bottom = Frame(self)
        bottom.pack(side = BOTTOM, fill = BOTH, expand = True)

        et_result = ExText(top)
        et_result.pack(side = LEFT, fill = BOTH, expand = True)
        self.et_result = et_result

        text = et_result.text
        text.configure(state = READONLY)
        text.tag_config("e", #ven
            background = "#FFFFFF",
        )
        text.tag_config("o", #dd
            background = "#DDDDDD",
        )
        text.tag_config("n", #on-ignored (normal)
            foreground = "#000000",
        )
        text.tag_config("i", #gnored
            foreground = "#888888",
        )

        text.bind("<Button-1>", self._on_res_b1)

        # Current PLY's Preprocessor does `trigraph` and `group_lines` on
        # input data.
        # This smashes token coordinates.
        """
        et_source = ExText(top)
        et_source.text.configure(state = READONLY)
        et_source.pack(side = RIGHT, fill = BOTH, expand = True)
        self.et_source = et_source
        """

        t_tag_info = GUIText(bottom, state = READONLY)
        bottom.rowconfigure(0, weight = 1)
        bottom.columnconfigure(0, weight = 1)
        t_tag_info.grid(row = 0, column = 0, sticky = "NESW")
        add_scrollbars_native(bottom, t_tag_info, sizegrip = True)
        self.t_tag_info = t_tag_info

        self.next_tag_i = 0
        self.tag2tok = {}

    def append_tokens(self, tokens):
        insert = self.et_result.insert
        tag2tok = self.tag2tok
        for last_tag_i, tok in enumerate(tokens, self.next_tag_i):
            tag = "tok" + str(last_tag_i)
            tag2tok[tag] = tok
            for c in tok.value:
                dc = decorate_ignored(c)
                insert(END, dc,
                    tag,
                    "o" if last_tag_i & 1 else "e",
                    "n" if c == dc else "i",
                )
        self.next_tag_i = last_tag_i + 1

    def _on_res_b1(self, e):
        text = e.widget
        tags = text.tag_names("@%d,%d" % (e.x, e.y))
        # print(", ".join(tags))
        for tag in tags:
            if tag.startswith("tok"):
                break
        else:
            self._show_tag_info("No token tag: " + ", ".join(tags))
            return

        tok = self.tag2tok[tag]

        file_path = tok_id2source.get(id(tok), "[unknown]")

        info = """\
Source: {file_path}
lexpos: {lexpos}
lineno: {lineno}
type  : {type}
        """.format(
            file_path = file_path,
            lexpos = tok.lexpos,
            lineno = tok.lineno,
            type = tok.type,
        )
        self._show_tag_info(info)

    def _show_tag_info(self, info):
        text = self.t_tag_info
        text.delete("0.0", END)
        text.insert(END, info)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument
    arg("input")
    arg("-I",
        action = "append",
        default = [],
        help = "extra CPP search path for #include",
        metavar = "include_dir",
    )
    args = ap.parse_args()

    i = args.input
    include_paths = args.I

    include_search_path = tuple(include_paths) + tuple(cpp_search_paths)

    print("Analyzing %r" % (i,))

    p = CAnalyzerPreprocessor(cpp_lexer_w)
    for __ in map(p.define, gcc_defines): pass
    for __ in map(p.add_path, include_search_path): pass

    in_data = p.read_include_file(i)
    p.parse(in_data, i)

    tokens = []
    append = tokens.append

    token = p.token
    tok = token()
    while tok:
        append(tok)
        tok = token()

    print("Tokens: %d" % (len(tokens),))

    w = CAnalyzerTk()
    w.title(basename(i) + " : " + dirname(i))
    w.append_tokens(tokens)
    w.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
