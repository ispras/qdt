__all__ = [
    "AutoVarTreeview"
]

from .tv_width_helper import (
    TreeviewWidthHelper,
)
from .var_widgets import (
    VarTreeview,
)


class AutoVarTreeview(VarTreeview, TreeviewWidthHelper):
    "A VarTreeview with column width manipulation helpers."

    def __init__(self, *a, **kw):
        VarTreeview.__init__(self, *a, **kw)
        TreeviewWidthHelper.__init__(self,
            auto_columns = kw.get("columns", ["#0"])
        )
