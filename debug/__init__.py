from common import (
    pypath,
)
from libe.common.import_all import (
    update_this,
)
update_this()

# this module uses custom pyelftools
with pypath("pyelftools"):
    from .this import *
