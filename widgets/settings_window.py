from .var_widgets import (
    VarLabel,
    VarButton
)
from common import (
    FormatVar,
    mlget as _
)
from .gui_frame import (
    GUIFrame
)
from .hotkey import (
    HKEntry
)
from six.moves.tkinter import (
    StringVar,
    BOTH
)
from qemu import (
    MOp_SetNodeVarNameBase
)
from .gui_toplevel import (
    GUIToplevel
)

class SettingsWidget(GUIFrame):
    def __init__(self, node, machine, *args, **kw):
        GUIFrame.__init__(self, *args, **kw)

        try:
            self.mht = self.winfo_toplevel().mht
        except AttributeError:
            # snapshot mode
            self.mht = None

        if self.mht is not None:
            self.mht.watch_changed(self.on_changed)

        self.node = node
        self.mach = machine

        self.node_fr = fr = GUIFrame(self)
        fr.pack(fill = BOTH, expand = False)
        fr.columnconfigure(0, weight = 0)
        fr.columnconfigure(1, weight = 1)

        # variable name base editing
        fr.rowconfigure(0, weight = 0)
        VarLabel(fr,
            text = _("Variable name base")
        ).grid(
            row = 0,
            column = 0,
            sticky = "NSW"
        )

        self.v_var_base = v = StringVar()
        HKEntry(fr,
            textvariable = v
        ).grid(
            row = 0,
            column = 1,
            sticky = "NESW"
        )

        fr.rowconfigure(1, weight = 0)
        VarLabel(fr,
            text = _("Name of variable")
        ).grid(
            row = 1,
            column = 0,
            sticky = "NSW"
        )

        HKEntry(fr,
            text = machine.node_id2var_name[node.id],
            state = "readonly"
        ).grid(
            row = 1,
            column = 1,
            sticky = "NESW"
        )

        self.refresh_after = self.after(0, self.__refresh_single__)

        self.bind("<Destroy>", self.__on_destroy__)

    def refresh(self):
        self.v_var_base.set(self.node.var_base)

    def apply(self):
        if self.mht is None:
            # apply have no effect in snapshot mode
            return

        self.mht.unwatch_changed(self.on_changed)

        prev_pos = self.mht.pos

        new_var_base = self.v_var_base.get()
        if new_var_base != self.node.var_base:
            self.mht.stage(MOp_SetNodeVarNameBase, new_var_base, self.node.id)

        self.__apply_internal__()

        if prev_pos is not self.mht.pos:
            # sequence description must be set during __apply_internal__
            self.mht.commit()

        self.mht.watch_changed(self.on_changed)

    def find_node_by_link_text(self, text):
        nid = text.split(":")[0]
        nid = int(nid)
        if nid < 0:
            return None
        else:
            return self.mach.id2node[nid]

    def __refresh_single__(self):
        self.refresh()
        del self.refresh_after

    def __on_destroy__(self, *args):
        if self.mht is not None:
            # the listener is not assigned in snapshot mode
            self.mht.unwatch_changed(self.on_changed)

        try:
            self.after_cancel(self.refresh_after)
        except AttributeError:
            pass

# Remembers runtime size of settings windows. One record per window type.
window_sizes = dict()

class SettingsWindow(GUIToplevel):
    def __init__(self, node, machine,
            machine_history_tracker = None,
            *args, **kw
        ):
        """ Toplevel.__init__ calls `title` which requires the attribute `node`
        to be initialized already. """
        self.node = node

        GUIToplevel.__init__(self, *args, **kw)

        self.mach = machine
        self.mht = machine_history_tracker

        self.grid()

        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 1)
        # to be set by child class constructor
        self.sw = None

        self.rowconfigure(1, weight = 0)

        fr = GUIFrame(self)
        fr.grid(
            row = 1,
            column = 0,
            sticky = "NES"
        )
        fr.rowconfigure(0, weight = 1)
        fr.columnconfigure(0, weight = 1)
        fr.columnconfigure(1, weight = 1)
        fr.columnconfigure(2, weight = 1)

        VarButton(fr,
            text = _("Refresh"),
            command = self.refresh
        ).grid(
            row = 0,
            column = 0,
            sticky = "S"
        )

        VarButton(fr,
            text = _("Apply"),
            command = self.apply
        ).grid(
            row = 0,
            column = 1,
            sticky = "S"
        )

        VarButton(fr, 
            text = _("OK"),
            command = self.apply_and_quit
        ).grid(
            row = 0,
            column = 2,
            sticky = "S"
        )

        # Makes settings window always on top.
        # Is there more pythonic interface?
        # http://effbot.org/tkinterbook/wm.htm#Tkinter.Wm.attributes-method
        self.attributes("-topmost", 1)

        self.bind("<Escape>", self.on_escape, "+")

        self.after(100, self.__init_geometry)

    def title(self, stringvar = None):
        """ Add the prefix with node ID. """
        if stringvar is None:
            return GUIToplevel.title(self, stringvar = stringvar)

        title = FormatVar("(%u) %%s" % self.node.id) % stringvar
        return GUIToplevel.title(self, stringvar = title)

    def on_escape(self, event):
        self.destroy()

    def refresh(self):
        self.sw.refresh()

    def apply(self):
        self.sw.apply()
        self.sw.refresh()

    def apply_and_quit(self):
        self.sw.apply()
        self.destroy()
 
    # Attempt to use @property + @sw.setter or __setattr__ has failed.
    # Maybe, because of Tkinter...
    def set_sw(self, value):
        if not self.sw is None:
            self.sw.unbind("<Destroy>", self.__on_sw_destroy__)
        if not value is None:
            value.bind("<Destroy>", self.__on_sw_destroy__, "+")
        self.sw = value

    def __on_sw_destroy__(self, event):
        self.destroy()

    def __init_geometry(self):
        init_size = (self.winfo_width(), self.winfo_height())

        size = window_sizes.get(type(self), None)
        if size is not None:
            size = max(size[0], init_size[0]), max(size[1], init_size[1])
            self.geometry("%ux%u" % size)

        self.bind("<Configure>", self.__on_configure, "+")

    def __on_configure(self, event):
        if event.widget is self:
            window_sizes[type(self)] = (event.width, event.height)

