from argparse import (
    ArgumentParser,
)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument
    arg("infile")
    arg("outfile")
    arg("prefix",
        nargs = "+",
    )
    arg("-w", "--max-width",
        default = 120,
        type = int,
    )
    arg("-t", "--tab-width",
        default = 4,
        type = int,
    )
    arg("-s", "--separator",
        default = " | ",
        type = str,
    )

    args = ap.parse_args()

    tab_width = args.tab_width
    tab_rep = " " * tab_width

    with open(args.infile, "r") as f:
        indata = f.read()
    indata = indata.replace("\t", tab_rep)

    prefixes = args.prefix

    prefix2index = tuple((p, i, len(p)) for (i, p) in enumerate(prefixes, 2))

    linecolumn = []

    for l in indata.splitlines():
        for p, i, skip in prefix2index:
            if l.startswith(p):
                l = l[skip:]
                break
        else:
            i = 1
        linecolumn.append((l, i))

    n_lines = len(linecolumn)
    lineno_len = len(str(n_lines))
    lineno_fmt = "%" + str(lineno_len) + "u "

    n_columns = len(prefixes) + 2

    max_width = args.max_width

    max_widths = [lineno_len + 1]

    headers = [""]
    for header in ["no prefix"] + prefixes:
        header = repr(header)
        lh = len(header)
        max_widths.append(lh)
        headers.append(header)

    for l, c in linecolumn:
        ll = len(l)
        if max_width < ll:
            ll = max_width
        if max_widths[c] < ll:
            max_widths[c] = ll

    separator = args.separator

    line_prefixes = []
    line_suffixes = []

    for i in range(n_columns):
        pfx = ""
        for k in range(0, i):
            pfx += " " * max_widths[k] + separator

        # space for line number
        pfx = pfx[max_widths[0]:]

        sfx = ""
        for k in range(i + 1, n_columns):
            sfx += separator + " " * max_widths[k]

        line_prefixes.append(pfx)
        line_suffixes.append(sfx)

    lines = []

    l = ""
    for i, h in enumerate(headers):
        if i:
            l += separator
        l += h
        l += " " * (max_widths[i] - len(h))

    lines.append(l)
    lines.append("")

    for lineno, (line, col) in enumerate(linecolumn):
        w = max_widths[col]
        while w < len(line):
            part = line[:w]
            line = line[w:]
            lines.append(
                  lineno_fmt % lineno
                + line_prefixes[col]
                + part
                + line_suffixes[col]
            )
        line += " " * (w - len(line))
        lines.append(
              lineno_fmt % lineno
            + line_prefixes[col]
            + line
            + line_suffixes[col]
        )

    with open(args.outfile, "w") as f:
        f.write("\n".join(l.rstrip() for l in lines))


if __name__ == "__main__":
    exit(main() or 0)
