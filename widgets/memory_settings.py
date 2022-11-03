__all__ = [
    "MemorySettingsWidget"
  , "MemorySettingsWindow"
]

from common import (
    mlget as _,
)
from .device_settings import (
    DeviceSettingsWidget,
)
from .gui_frame import (
    GUIFrame,
)
from .hotkey import (
    HKEntry,
)
from qemu import (
    MachineNodeOperation,
    MemoryAliasNode,
    MemoryLeafNode,
    MemoryNode,
    MemoryRAMNode,
    MemoryROMNode,
    MemorySASNode,
    MOp_AddMemChild,
    MOp_RemoveMemChild,
    MOp_SetMemNodeAlias,
    MOp_SetMemNodeAttr,
    QemuTypeName,
)
from .settings_window import (
    SettingsWidget,
    SettingsWindow,
)
from source import (
    CConst,
)
from .var_widgets import (
    VarCheckbutton,
    VarLabel,
)

from six.moves.tkinter import (
    BooleanVar,
    BOTH,
    StringVar,
)
from six.moves.tkinter_ttk import (
    Combobox,
)


def name_to_var_base(name):
    type_base = "sas" if "System address space" in name else name
    qtn = QemuTypeName(type_base)
    return qtn.for_id_name


# `object` is for `property`
class MemorySettingsWidget(SettingsWidget, object):
    def __init__(self, mem, *args, **kw):
        SettingsWidget.__init__(self, mem, *args, **kw)

        self.mem_fr = fr = GUIFrame(self)
        fr.pack(fill = BOTH, expand = False)

        fr.columnconfigure(0, weight = 0)
        fr.columnconfigure(1, weight = 1)
        fr.rowconfigure(0, weight = 0)
        row = 0

        l = VarLabel(fr, text = _("Region type"))
        l.grid(row = row, column = 0, sticky = "NES")

        memtype2str = {
           MemoryNode: _("Container"),
           MemorySASNode: _("SAS"),
           MemoryAliasNode: _("Alias"),
           MemoryRAMNode: _("RAM"),
           MemoryROMNode: _("ROM")
        }

        l = VarLabel(fr, text = memtype2str[ type(mem) ])
        l.grid(row = row, column = 1, sticky = "NEWS")
        row += 1

        if not isinstance(mem, MemorySASNode):
            l = VarLabel(fr, text = _("Parent region"))
            l.grid(row = row, column = 0, sticky = "NES")

            self.var_parent = StringVar()
            self.cb_parent = Combobox(fr,
                textvariable = self.var_parent,
                state = "readonly"
            )
            self.cb_parent.grid(row = row, column = 1, sticky = "NEWS")
            row += 1

        self.fields = [
            (_("Name"), "name", CConst),
            (_("Size"), "size", CConst),
            (_("Offset"), "offset", CConst),
            (_("May overlap"), "may_overlap", bool),
            (_("Priority"), "priority", CConst)
        ]

        if type(mem) is MemoryAliasNode:
            self.fields.extend([ (_("Alias offset"), "alias_offset", CConst) ])

        if isinstance(mem, MemorySASNode):
            self.fields = [(_("Name"), "name", str)]

        for text, field, _type in self.fields:
            if _type is bool:
                l = None
                v = BooleanVar()
                w = VarCheckbutton(fr, text = text, variable = v)
            else:
                l = VarLabel(fr, text = text)
                v = StringVar()
                w = HKEntry(fr, textvariable = v)

            fr.rowconfigure(row, weight = 0)
            if l is None:
                w.grid(row = row, column = 0, sticky = "NWS",
                    columnspan = 2
                )
            else:
                l.grid(row = row, column = 0, sticky = "NES")
                l.gi = l.grid_info()
                w.grid(row = row, column = 1, sticky = "NEWS")
            w.gi = w.grid_info()
            row += 1

            if l:
                setattr(self, "l_" + field, l)
            setattr(self, "w_" + field, w)
            setattr(self, "var_" + field, v)

        self.var_name.trace_variable("w", self.__on_name_var_changed)

        if type(mem) is MemoryAliasNode:
            l = VarLabel(fr, text = _("Alias region"))
            l.grid(row = row, column = 0, sticky = "NES")

            self.var_alias_to = StringVar()
            self.cb_alias_to = Combobox(fr,
                textvariable = self.var_alias_to,
                state = "readonly"
            )
            self.cb_alias_to.grid(row = row, column = 1, sticky = "NEWS")

        if not isinstance(mem, MemorySASNode):
            if not mem.parent:
                self.l_offset.grid_forget()
                self.w_offset.grid_forget()

    @property
    def mem(self):
        return self.node

    def __apply_internal__(self):
        mem = self.node

        if not isinstance(mem, MemorySASNode):
            new_parent = self.find_node_by_link_text(self.var_parent.get())
            cur_parent = mem.parent

            if new_parent is None:
                new_parent_id = -1
            else:
                new_parent_id = new_parent.id

            if cur_parent is None:
                cur_parent_id = -1
            else:
                cur_parent_id = cur_parent.id

            if not new_parent_id == cur_parent_id:
                if not cur_parent_id == -1:
                    self.mht.stage(
                        MOp_RemoveMemChild,
                        mem.id,
                        cur_parent_id
                    )
                if not new_parent_id == -1:
                    self.mht.stage(MOp_AddMemChild, mem.id, new_parent_id)

        for __, field, _type in self.fields:
            new_val = getattr(self, "var_" + field).get()
            if _type is CConst:
                try:
                    new_val = CConst.parse(new_val)
                except:
                    continue

            cur_val = getattr(mem, field)

            if new_val == cur_val:
                continue

            self.mht.stage(MOp_SetMemNodeAttr, field, new_val, mem.id)

        if type(mem) is MemoryAliasNode:
            new_alias_to = self.find_node_by_link_text(self.var_alias_to.get())
            cur_alias_to = mem.alias_to

            if not new_alias_to == cur_alias_to:
                self.mht.stage(
                    MOp_SetMemNodeAlias,
                    "alias_to",
                    new_alias_to,
                    mem.id
                )

        self.mht.set_sequence_description(
            _("Memory '%s' (%d) configuration.") % (
                mem.name, mem.id
            )
        )

    def refresh(self):
        SettingsWidget.refresh(self)

        smem = self.node

        if not isinstance(smem, MemorySASNode):
            values = [
                DeviceSettingsWidget.gen_node_link_text(mem) for mem in (
                    [
                        mem for mem in self.mach.mems if (
                            not isinstance(mem, MemoryLeafNode)
                            and mem != smem
                        )
                    ] + [ None ]
                )
            ]

            self.cb_parent.config(values = values)

            self.var_parent.set(
                DeviceSettingsWidget.gen_node_link_text(smem.parent)
            )

        for __, field, _type in self.fields:
            var = getattr(self, "var_" + field)
            cur_val = getattr(smem, field)
            var.set(cur_val)

        if type(smem) is MemoryAliasNode:
            values = [
                DeviceSettingsWidget.gen_node_link_text(mem) for mem in (
                    [ mem for mem in self.mach.mems if (mem != smem) ]
                )
            ]

            self.cb_alias_to.config(values = values)

            self.var_alias_to.set(
                DeviceSettingsWidget.gen_node_link_text(smem.alias_to)
            )

        if not isinstance(smem, MemorySASNode):
            if smem.parent is None:
                self.l_offset.grid_forget()
                self.w_offset.grid_forget()
            else:
                self.l_offset.grid(self.l_offset.gi)
                self.w_offset.grid(self.w_offset.gi)

    def on_changed(self, op, *__, **___):
        if not isinstance(op, MachineNodeOperation):
            return

        if op.writes_node() and self.node.id == -1:
            self.destroy()
        else:
            self.refresh()

    def __on_name_var_changed(self, *__):
        vvb = self.v_var_base
        vb = vvb.get()

        try:
            prev_n = self.__prev_name
        except AttributeError:
            # name was not edited yet
            prev_n = self.node.name.v

        if vb == "mem" or vb == name_to_var_base(prev_n):
            """ If current variable name base is default or corresponds to
            previous name then auto suggest new variable name base
            with account of just entered name. """
            n = self.var_name.get()
            vvb.set(name_to_var_base(n))
            self.__prev_name = n

class MemorySettingsWindow(SettingsWindow):
    def __init__(self, mem, *args, **kw):
        SettingsWindow.__init__(self, mem, *args, **kw)

        self.title(_("Memory settings"))

        self.set_sw(MemorySettingsWidget(mem, self.mach, self))
        self.sw.grid(row = 0, column = 0, sticky = "NEWS")
