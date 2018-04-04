from six.moves.tkinter import (
    Frame
)
from .tk_unbind import (
    unbind
)

class GUIFrame(Frame):
    unbind = unbind

    def __init__(self, *args, **kwargs):
        Frame.__init__(self, *args, **kwargs)
