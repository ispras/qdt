from libe.grammars.antlr.v4 import (
    parser,
)

from argparse import (
    ArgumentParser,
)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("antlr_file",
        nargs = "+",
    )

    args = ap.parse_args()

    antlr_file = args.antlr_file

    for antlr_file in args.antlr_file:
        with open(antlr_file, "r") as f:
            content = f.read()
    
        ast = parser.parse(content)
        print(ast)


if __name__ == "__main__":
    exit(main() or 0)
