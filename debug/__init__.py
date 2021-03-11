from common import (
    pypath,
    update_this,
)
update_this()

# this module uses custom pyelftools
with pypath("pyelftools"):
    from .this import *
