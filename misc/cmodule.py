from common import (
    def_tokens,
)
from source import (
    simple_c_lexer,
    simple_c_parser,
)
from sysconfig import (
    get_config_var,
    get_paths,
)
"""
gcc -shared -o test_cmodule.so $(pkg-config --cflags python3) test_cmodule.c \
    $(pkg-config --libs python3)
"""
import misc.test_cmodule as cmod


def parse_code(code, **kw):
    return simple_c_parser.parse(code,
        lexer = simple_c_lexer,
        **kw
    )


class CModule(object):

    def __init__(self, file_name):
        self.file_name = file_name

        with open(self.file_name, "r") as f:
            code_text = f.read()

        try:
            res = parse_code(code_text)
        except:
            parse_code(code_text, debug = True)
            assert False # must not be reqched because of error in parse_code

        print(res)


def main():
    print(get_config_var("CFLAGS"))
    paths = get_paths()
    print(paths["include"])
    print(dir(cmod))
    print(cmod.system("ls -al"))

    CModule("mod.c")

if __name__ == "__main__":
    exit(main() or 0)
