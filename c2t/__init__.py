from common import (
    pypath,
)
from libe.common.import_all import (
    update_this,
)
update_this()

# This module uses pyrsp which import elftools. It must import our elftools.
with pypath("..debug.pyelftools"):
    from .this import *
