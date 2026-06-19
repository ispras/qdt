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

    def __init__(self, rsp, bins, args):
        """
@param rsp:
    A callable that returns `debug.runtime.Runtime` compatible `target`.
    E.g., a `debug.qrsp.QRSP` sub`class`.
@param bins:
    An iterable of binary files to process.
@qargs args:
    An iterable of arguments for `Popen` to run the emulator.
    It must define an option to load a target code from file {bin}.
    E.g., `"-kernel", "{bin}"`.
        """
        type(self).configs.append(self)
        self.rsp = rsp
        self.bins = list(bins)
        self.args = list(args)


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
