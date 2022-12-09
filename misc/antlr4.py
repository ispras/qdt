from libe.grammars.antlr.to_lark import (
    ANTLR2Lark,
)
from libe.grammars.antlr.v4 import (
    parser,
)
from widgets import (
    add_scrollbars_native,
    GUITk,
)

from argparse import (
    ArgumentParser,
)
from lark.tree import (
    Tree,
)
from multiprocessing import (
    Process,
    Queue,
)
from os.path import (
    split,
)
from queue import (
    Empty,
)
from six.moves.tkinter import (
    BOTH,
    END,
    Frame,
)
from six.moves.tkinter_ttk import (
    Notebook,
    Treeview,
)
from sys import (
    stdout,
)
from traceback import (
    print_exc,
)


def iter_dup(v):
    while True:
        yield v


def iter_fill_tv(tv, ast):
    queue = [("", ast)]

    while queue:
        yield

        piid, n = queue.pop(0)

        if isinstance(n, Tree):
            data = n.data
        else:
            data = n

        niid = tv.insert(piid, END,
            text = data.value,
            values = [
                data.type,
            ]
        )

        if isinstance(n, Tree):
            queue.extend(zip(iter_dup(niid), n.children))


def co_fill_tree(tv, ast):
    for i, __ in enumerate(iter_fill_tv(tv, ast)):
        if not (i & 0xFF):
            yield


def parse(file, q):
    print("reading %s" % file)
    with open(file, "r") as f:
        content = f.read()
    print("parsing %s" % file)
    ast = parser.parse(content)
    print("parsed %s" % file)
    q.put(ast)
    print("terminating")


def co_parse(root, files, output):
    if output is None:
        of = stdout
    else:
        of = open(output, "w")

    tabs = Notebook(root)
    tabs.pack(fill = BOTH, expand = True)

    q = Queue()

    for file in files:
        yield

        print("starting process for %s" % file)
        p = Process(target = parse, args = (file, q))
        p.start()

        while p.pid is None:
            yield

        print("process %d for %s started, waiting" % (p.pid, file))

        ast = None
        while p.exitcode is None:
            try:
                ast = q.get(False)
                break
            except Empty:
                yield

        if p.exitcode is not None and p.exitcode != 0:
            print("process %d failed for %s with code %d" % (
                p.pid, file, p.exitcode
            ))
            continue

        while ast is None:
            try:
                ast = q.get(False)
            except Empty:
                yield

        print("AST for %s is ready" % (file,))

        while p.exitcode is None:
            yield

        print("process %d for %s succeeded" % (p.pid, file))
        # p.close()

        __, name = split(file)

        fr = Frame(tabs)
        tabs.add(fr, text = name)
        tv = Treeview(fr,
            columns = ("kind",)
        )
        tv.item("", open = True)

        fr.columnconfigure(0, weight = 1)
        fr.rowconfigure(0, weight = 1)
        tv.grid(row = 0, column = 0, sticky = "NESW")
        add_scrollbars_native(fr, tv, sizegrip = True)

        root.enqueue(co_fill_tree(tv, ast))

        yield

        t = ANTLR2Lark()
        try:
            res = t.transform(ast)
        except:
            print_exc()
        else:
            of.write("// %s \n\n" % file)
            of.write(res + "\n")

    if of is not stdout:
        of.close()

    q.close()
    q.join_thread()


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("antlr_file",
        nargs = "+",
    )
    arg("-o", "--output",
        nargs = "?",
        default = None,
    )

    args = ap.parse_args()

    root = GUITk()
    root.title("ANTLR4 View")
    root.geometry("600x600")

    root.enqueue(co_parse(root, args.antlr_file, args.output))
    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
