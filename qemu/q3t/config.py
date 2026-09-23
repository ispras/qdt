__all__ = [
    "read_q3t_config"
  , "Q3T"
]

from os.path import (
    abspath,
    dirname,
)

# for `read_q3t_config`
from c2t.config import *
from debug.qrsp import *


class Q3T(object):
    "Qemu Target Test Tool configuration"

    configs = []

    def __init__(self, rsp, bins, args,
        bp_infix = None,
        expr_prefix = None,
    ):
        """
@param rsp:
    A callable that returns `debug.runtime.Runtime` compatible `target`.
    E.g., a `debug.qrsp.QRSP` sub`class`.

@param bins:
    An iterable of binary files to process.

@param args:
    An iterable of arguments for `Popen` to run the emulator.
    It must define an option to load a target code from file {bin}.
    E.g., `"-kernel", "{bin}"`.

@param bp_infix:
    A `re`gular expression.
    The value prevails default value.
    CLI explicit value prevails the value.

    A break point is set on each symbol with matching substring in its name.

@param expr_prefix:
    A `re`gular expression.
    The value prevails default value.
    CLI explicit value prevails the value.

    The tail of a string after matching substring is run as a Python
    expression on nearby break point stop.
    `if not (the expression)` then a failure is accounted.
    An `except`ion during the expression `eval`uation is a failure too.
    Multiple expressions for a break point is allowed.
    They are evaluated in line number ascending order.

    Nearness between an expression and corresponding break point is not
    strictly defined and depends on debug information by
    the assembler (compiler).
    Keep expressions as near as possible to its break point symbols (labels)
    and insert enough instructions (statements) between break points.

    Note that C language labels are not exported as symbols, use functions.

        """
        type(self).configs.append(self)
        self.rsp = rsp
        self.bins = list(bins)
        self.args = list(args)
        self.bp_infix = bp_infix
        self.expr_prefix = expr_prefix


def read_q3t_config(config_file_path):
    config_file_path = abspath(config_file_path)
    config_dir_path = dirname(config_file_path)

    with open(config_file_path, "r") as f:
        config_src = f.read()

    config_code = compile(config_src, config_file_path, "exec")

    config_ns = dict()
    config_glob = dict(globals())
    config_glob["__file__"] = config_file_path

    exec(config_code, config_ns, config_glob)

    for config in Q3T.configs:
        config.file_path = config_file_path
        config.dir_path = config_dir_path

    n = len(Q3T.configs)
    if n < 1:
        raise Exception("No `Q3T` instance created %r" % config_file_path)
    if n > 1:
        raise NotImplementedError("Only 1 `Q3T` instance supported")

    return config
