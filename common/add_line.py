__all__ = [
    "add_line"
  , "add_line_to_file"
]


def add_line(lines, line):
    "Appends `line` to `lines` if such a line is absent."

    if line in lines:
        return
    lines.append(line)


def add_line_to_file(file_name, line):
    "Appends `line` to file named `file_name` if such a line is absent."

    if line[-1] != '\n':
        line += '\n'

    with open(file_name, "r") as f:
        lines = f.readlines()

    add_line(lines, line)

    with open(file_name, "w") as f:
        f.write("".join(lines))
