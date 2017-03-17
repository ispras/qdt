from .var_widgets import \
    VarMenu, \
    VarTreeview

from qemu import \
    MemoryNode, \
    MemoryLeafNode, \
    MemoryAliasNode, \
    MemoryRAMNode, \
    MemoryROMNode

from common import \
    mlget as _

from .popup_helper import \
    TkPopupHelper

from six import \
    integer_types

class MemoryTreeWidget(VarTreeview, TkPopupHelper):
    def __init__(self, mach_desc, *args, **kw):
        VarTreeview.__init__(self, *args, **kw)
        TkPopupHelper.__init__(self)

        mach_desc.link()

        self.mach = mach_desc
        try:
            pht = self.winfo_toplevel().pht
        except AttributeError:
            self.mht = None
        else:
            if pht is None:
                self.mht = None
            else:
                self.mht = pht.get_machine_proxy(self.mach)

        # snapshot mode without MHT
        if self.mht is not None:
            pass
            # TODO: watch machine changes and update map on relevant changes
            # TODO: remove watching callback

        self.iid2node = {}
        self.selected = None

        self["columns"] = ("id", "offset", "size", "type")

        self.heading("#0", text = _("Name"))
        self.heading("id", text = _("Id"))
        self.heading("offset", text = _("Offset"))
        self.heading("size", text = _("Size"))
        self.heading("type", text = _("Type"))

        self.bind("<ButtonPress-3>", self.on_b3_press)

        p0 = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p1 = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p2 = VarMenu(self.winfo_toplevel(), tearoff = 0)
        p3 = VarMenu(self.winfo_toplevel(), tearoff = 0)

        for command in [
            _("Settings"),
            _("Delete")
        ]:
            p0.add_command(
                label = command,
                command = self.on_popup_node_settings
            )

            """ All commands should follow consequent rule. If a command
does action immediately then it should be disabled in snapshot mode like this
command. If a command shows a dialog then either the dialog should support
snapshot mode or the command should be disabled too.
            """
            p1.add_command(
                label = command,
                command = self.notify_popup_command if self.mht is None else \
                    self.on_popup_node_delete
            )

        c0 = VarMenu(p1, tearoff = 0)
        c1 = VarMenu(p2, tearoff = 0)
        for memory_type in [
            _("Container"),
            _("RAM"),
            _("ROM"),
            _("Alias")
        ]:
            c0.add_command(
                label = memory_type,
                command = getattr(self, "on_add_" +
                    memory_type.key_value.lower().replace(" ", "_").\
                        replace("-", "_")
                )
            )
            c1.add_command(
                label = memory_type,
                command = getattr(self, "on_add_" +
                    memory_type.key_value.lower().replace(" ", "_").\
                        replace("-", "_")
                )
            )

        p1.add_cascade(
            label = _("Add node"),
            menu = c0
        )

        p2.add_cascade(
            label = _("Add node"),
            menu = c1
        )

        p3.add_command(
            label = _("Select origin"),
            command = self.on_select_origin
        )

        self.popup_leaf_node = p0
        self.popup_not_leaf_node = p1
        self.popup_empty = p2
        self.popup_temp_node = p3

        self.after(0, self.widget_initialization)

    def on_popup_node_settings(self):
        # TODO
        self.notify_popup_command()

    def on_popup_node_delete(self):
        # TODO
        self.notify_popup_command()

    def on_add_container(self):
        # TODO
        self.notify_popup_command()

    def on_add_ram(self):
        # TODO
        self.notify_popup_command()

    def on_add_rom(self):
        # TODO
        self.notify_popup_command()

    def on_add_alias(self):
        # TODO
        self.notify_popup_command()

    def on_select_origin(self):
        self.selection_set(self.selected.id)
        self.focus(self.selected.id)
        self.see(self.selected.id)

    def widget_initialization(self):
        self.delete(*self.get_children())

        self.iid2node.clear()
        mems_queue = [m for m in self.mach.mems if not m.parent]
        unprocessed_mems = list(self.mach.mems)
        memtype2str = {
           MemoryNode: "Container",
           MemoryAliasNode: "Alias",
           MemoryRAMNode: "RAM",
           MemoryROMNode: "ROM"
        }

        while unprocessed_mems:
            while mems_queue:
                m = mems_queue.pop(0)
                try:
                    unprocessed_mems.remove(m)
                except ValueError:
                    ml_text = _("LOOP")
                    self.insert(m.parent.id, "end",
                        iid = str(m.id) + ".loop",
                        text = m.name + " (" + ml_text.get() + ")",
                        tags = ("loop")
                    )
                else:
                    def hwaddr_val(val):
                        if isinstance(val, integer_types):
                            return hex(val)
                        else:
                            return str(val)

                    parent_id = ""
                    if m.parent and self.exists(m.parent.id):
                        parent_id = m.parent.id

                    self.insert(parent_id, "end",
                        iid = m.id,
                        text = m.name,
                        values = (
                            m.id,
                            hwaddr_val(m.offset),
                            hwaddr_val(m.size),
                            memtype2str[type(m)]
                        )
                    )

                    if isinstance(m, MemoryAliasNode):
                        self.insert(m.id, "end",
                            iid =  str(m.alias_to.id) + "." + str(m.id),
                            text = m.alias_to.name,
                            values = ("", hwaddr_val(m.alias_offset),),
                            tags = ("alias")
                        )

                    mems_queue.extend(m.children)
                    self.iid2node[str(m.id)] = m

            if unprocessed_mems:
                mems_queue = [unprocessed_mems[0]]

        self.tag_configure("loop", foreground = "red")
        self.tag_configure("alias", foreground = "grey")

    def on_b3_press(self, event):
        iid = self.identify_row(event.y)
        """ TODO: when user clicks over a row, the row should be be selected
        in the tree view. This prevents confusion of row for which the popup
        is shown. """

        try:
            self.selected = self.iid2node[iid]

            if isinstance(self.selected, MemoryLeafNode):
                popup = self.popup_leaf_node
            else:
                popup = self.popup_not_leaf_node
        except:
            if "." in iid:
                self.selected = self.iid2node[iid.split(".", 1)[0]]
                popup = self.popup_temp_node
            else:
                self.selected = None
                popup = self.popup_empty

        self.show_popup(event.x_root, event.y_root, popup, self.selected)

        # print("on_b3_press")

    def gen_layout(self):
        return None

    def set_layout(self, layout):
        assert layout is None
