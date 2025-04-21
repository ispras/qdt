__all__ = [
    "add_line"
  , "add_line_to_file"
]


def add_line(lines, line, after = -1):
    """ Inserts `line` to `lines` if such a line is absent.
`return`s `bool` indicating `line` insertion.
    """

    if line in lines:
        return False
    lines.insert(after, line)
    return True


def add_line_to_file(file_name, line, *a, **kw):
    "Inserts `line` to file named `file_name` if such a line is absent."

    if line[-1] != '\n':
        line += '\n'

    with open(file_name, "r") as f:
        lines = f.readlines()

    if add_line(lines, line, *a, **kw):
        with open(file_name, "w") as f:
            f.write("".join(lines))
