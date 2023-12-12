__all__ = [
    "Statusbar"
]

from .gui_frame import (
    GUIFrame,
)
from .pack_info_compat import (
    pack_info,
)
from .var_widgets import (
    VarLabel,
)

from six.moves.tkinter import (
    Label,
    LEFT as SIDE_LEFT,
    RIGHT as SIDE_RIGHT,
    SUNKEN as RELIEF_SUNKEN,
    W as ANCHOR_W,
    X as FILL_X,
)


class Statusbar(GUIFrame):

    def __init__(self, *args, **kw):
        GUIFrame.__init__(self, *args, **kw)

        # Empty status bar still must get its space in parent widget.
        self.padding = Label(self)
        self.padding.pack(fill = FILL_X, expand = 1, side = SIDE_RIGHT)

    def _gen_label(self, string_var, **lb_args):
        return VarLabel(self,
            bd = 1,
            relief = RELIEF_SUNKEN,
            anchor = ANCHOR_W,
            textvariable = string_var,
            **lb_args
        )

    def repack(self, widget, side):
        """ Original 'pack' method adds widgets from the `side` of the frame to
its center. E.g. a new widget packed with flag `RIGHT` is appended at the left
of any other widget added to the RIGHT side before it. I.e. to add a new widget
at the right (left) of any other, all packed widgets must be repacked and
the new widget must be added before them.

    This method also takes into account padding label.
        """

        slaves = list(self.pack_slaves())

        sides = [side]

        for slave in slaves:
            sides.append(pack_info(slave)["side"])
            slave.pack_forget()

        slaves.insert(0, widget)

        for slave, side, junk in zip(slaves, sides, range(0, len(slaves)-1)):
            slave.pack(fill = FILL_X, side = side)

        self.padding.pack(fill = FILL_X, expand = 1, side = SIDE_RIGHT)

    def right(self, string_var, **lb_args):
        lb = self._gen_label(string_var, **lb_args)
        self.repack(lb, SIDE_RIGHT)
        return lb

    def left(self, string_var, **lb_args):
        lb = self._gen_label(string_var, **lb_args)
        self.repack(lb, SIDE_LEFT)
        return lb
