# This module have no a content. During importing, it adds the path of `ply`
# submodule to `sys.path` allowing importing of `ply` package.
#
# Usage example #1:
#
# from common.ply2path import *
# import ply
#
# Usage example #2:
#
# from common import (
#     ply2path
# )
# import ply
#
# This way you do have "ply2path" name defined in global scope.

__all__ = []

from os.path import (
    split,
    join
)
from sys import (
    path
)

ply_path = join(split(split(split(__file__)[0])[0])[0], "ply")
if ply_path not in path:
    path.insert(0, ply_path)
