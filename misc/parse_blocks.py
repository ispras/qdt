#!/usr/bin/env python3

from common import (
    bidict,
)
from source import (
    BlockParser,
)

from argparse import (
    ArgumentParser,
)
from collections import (
    deque,
)
from traceback import (
    print_exc,
)


class Line2GVNode(bidict):

    n = 0
    def __missing__(self, line):
        n = self.n
        node = "N" + str(n)
        self.n = n + 1
        self[line] = node
        return node


def gv_escape(s):
    return "".join(iter_gv_escape(s))

def iter_gv_escape(s):
    for c in s:
        if c == "<":
            yield "&lt;"
        elif c == ">":
            yield "&gt;"
        elif c == "&":
            yield "&amp;"
        else:
            yield c

def gv_label(s):
    return "<" + gv_escape(s) + ">"


def main():
    ap = ArgumentParser(
        description = """\
Parses indentation block structure of a text file and returns graph
(Graphviz) of the file structure."""
        ,
    )
    arg = ap.add_argument

    arg("input",
        action = "extend",
        nargs = "*",
    )

    args = ap.parse_args()

    inputs = args.input
    if not inputs:
        inputs.append(__file__)

    for file_path in inputs:
        try:
            with open(file_path, "r") as f:
                file_data = f.read()
        except:
            print_exc()
            continue

        top = BlockParser().parse(file_data)
        top.n = -1  # to be sortable with `int`s

        gv_lines = []
        l = gv_lines.append

        l2n = Line2GVNode()

        l("digraph G {")
        l('\trankdir="LR"')
        l("\tnode [shape=box fontname=monospace]")

        queue = deque()
        _extend = queue.extend
        def extend(line):
            line_block = line.child
            if not line_block:
                return
            _extend((line, child) for child in line_block)
        popleft = queue.popleft

        l("\t%s [label=%s]" % (l2n[top.n], gv_label(file_path)))
        extend(top)

        while queue:
            parent_line, child_line = popleft()

            l("\t%s [label=%s]" % (
                l2n[child_line.n],
                gv_label(str(child_line)),
            ))
            l("\t%s -> %s [label=%s]" % (
                l2n[parent_line.n],
                l2n[child_line.n],
                gv_label(str(child_line.n)),
            ))

            extend(child_line)

        l("}")

        out_path = file_path + ".gv"
        gv_txt = "\n".join(gv_lines)

        with open(out_path, "w") as f:
            f.write(gv_txt)


if __name__ == "__main__":
    exit(main() or 0)
