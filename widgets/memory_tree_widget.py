from .var_widgets import \
    VarMenu, \
    VarTreeview

from qemu import \
    MemoryNode, \
    MemorySASNode, \
    MemoryLeafNode, \
    MemoryAliasNode, \
    MemoryRAMNode, \
    MemoryROMNode, \
    MachineNodeOperation, \
    MOp_AddMemoryNode, \
    MOp_DelMemoryNode, \
    MOp_AddMemChild, \
    MOp_RemoveMemChild, \
    MOp_SetMemNodeAlias, \
    MOp_SetMemNodeAttr

from .memory_settings import \
    MemorySettingsWindow

from common import \
    mlget as _

from .popup_helper import \
    TkPopupHelper

from six import \
    integer_types

from six.moves.tkinter import \
    TclError

from .tk_unbind import \
    unbind

LAYOUT_COLUMNS_WIDTH = "columns width"

memtype2str = {
    MemoryNode: "Container",
    MemorySASNode : "System address space",
    MemoryAliasNode: "Alias",
    MemoryRAMNode: "RAM",
    MemoryROMNode: "ROM"
}

class MultipleSASInMachine(Exception):
    pass

def hwaddr_val(val):
    if isinstance(val, integer_types):
        return hex(val)
    else:
        return str(val)

class DraggedLabel(VarMenu):
    def __init__(self, parent):
        VarMenu.__init__(self, parent, tearoff = 0)
        self.add_command()
        self.displayed = False
        self.padding = 10

    def show(self, event):
        if not self.displayed:
            self.displayed = True
            self.post(event.x_root + self.padding, event.y_root)

    def hide(self):
        if self.displayed:
            self.displayed = False
            self.unpost()

    def move(self, event):
        if self.displayed:
            self.post(event.x_root + self.padding, event.y_root)

    def set_text(self, text):
        self.entryconfig(0, label = text)

class MemoryTreeWidget(VarTreeview, TkPopupHelper):
    def __init__(self, mach_desc, *args, **kw):
        VarTreeview.__init__(self, *args, **kw)
        TkPopupHelper.__init__(self)

        mach_desc.link(handle_system_bus = False)

        self.mach = mach_desc

        toplevel = self.winfo_toplevel()
        try:
            self.hk = toplevel.hk
        except AttributeError:
            self.hk = None

        try:
            pht = toplevel.pht
        except AttributeError:
            self.mht = None
        else:
            if pht is None:
                self.mht = None
            else:
                self.mht = pht.get_machine_proxy(self.mach)

        # snapshot mode without MHT
        if self.mht is not None:
            self.mht.watch_changed(self.on_machine_changed)

        self.iid2node = {}
        self.selected = None

        self.dragged_iid = None
        self.old_parent = None
        self.old_index = None
        self.highlighted_path = []
        self.sas_dnd = False
        self.dragged_label = DraggedLabel(self)

        self.tag_configure("loop", foreground = "red")
        self.tag_configure("alias", foreground = "grey")
        self.tag_configure("places", foreground = "green")

        self["columns"] = ("id", "offset", "size", "type")

        self.heading("#0", text = _("Name"))
        self.heading("id", text = _("Id"))
        self.heading("offset", text = _("Offset"))
        self.heading("size", text = _("Size"))
        self.heading("type", text = _("Type"))

        self.popup_leaf_node = p0 = VarMenu(self.winfo_toplevel(), tearoff = 0)
        self.popup_not_leaf_node = p1 = VarMenu(self.winfo_toplevel(),
            tearoff = 0
        )
        self.popup_empty = p2 = VarMenu(self.winfo_toplevel(), tearoff = 0)
        self.popup_temp_node = p3 = VarMenu(self.winfo_toplevel(), tearoff = 0)

        for menu in [
            p0, p1
        ]:
            menu.add_command(
                label = _("Alias target"),
                command = self.on_popup_node_alias_target
            )
            menu.add_separator()
            menu.add_command(
                label = _("Settings"),
                command = self.on_popup_node_settings
            )

            """ All commands should follow consequent rule. If a command
does action immediately then it should be disabled in snapshot mode like this
command. If a command shows a dialog then either the dialog should support
snapshot mode or the command should be disabled too.
            """
            menu.add_separator()
            menu.add_command(
                label = _("Delete"),
                command = self.notify_popup_command if self.mht is None else \
                    self.on_popup_node_delete
            )
        p1.add_separator()

        self.popup_not_leaf_node_submenu = c0 = VarMenu(p1, tearoff = 0)
        self.popup_empty_submenu = c1 = VarMenu(p2, tearoff = 0)

        self.alias_to = None

        for memory_type in [
            _("Container"),
            _("RAM"),
            _("ROM")
        ]:
            c0.add_command(
                label = memory_type,
                command = self.notify_popup_command if self.mht is None else \
                    getattr(self, "on_add_" +
                    memory_type.key_value.lower().replace(" ", "_").\
                        replace("-", "_")
                )
            )
            c1.add_command(
                label = memory_type,
                command = self.notify_popup_command if self.mht is None else \
                    getattr(self, "on_add_" +
                    memory_type.key_value.lower().replace(" ", "_").\
                        replace("-", "_")
                )
            )

        for menu in [
            c0, c1
        ]:
            menu.add_command(
                label = _("Alias"),
                command = self.notify_popup_command if self.mht is None else \
                    self.on_add_alias,
                state = "disabled"
            )

        sas = None

        for mem in self.mach.mems:
            if isinstance(mem, MemorySASNode):
                if sas is None:
                    sas = mem
                elif not sas == mem:
                    raise MultipleSASInMachine()

        c1.add_command(
            label = _("SAS"),
            command = self.notify_popup_command if self.mht is None else \
                self.on_add_sas,
            state = "normal" if sas is None else "disabled"
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

        self.bind("<Destroy>", self.__on_destroy__, "+")
        self.bind("<B1-Motion>", self.on_b1_move)

        self.enable_hotkeys()

        self.widget_initialization()

    def __on_destroy__(self, *args, **kw):
        if self.mht is not None:
            # the listener is assigned only in non-snapshot mode
            self.mht.unwatch_changed(self.on_machine_changed)

    def disable_hotkeys(self):
        if self.hk:
            self.hk.disable_hotkeys()

        self.unbind("<ButtonPress-3>")
        self.unbind("<Double-Button-1>")
        unbind(self, "<Delete>", self.__on_key_delete)

    def enable_hotkeys(self):
        if self.hk:
            self.hk.enable_hotkeys()

        self.bind("<ButtonPress-3>", self.on_b3_press)
        self.bind("<Double-Button-1>", self.on_b1_double)
        self.__on_key_delete = self.bind("<Delete>", self.on_key_delete, "+")

    def on_machine_changed(self, op):
        if not isinstance(op, MachineNodeOperation):
            return

        if op.sn != self.mach.__sn__:
            return

        if op.writes_node():
            if (self.alias_to and self.alias_to.id == -1) or not self.alias_to:
                self.alias_to = None
                self.popup_not_leaf_node_submenu.entryconfig(
                    3,
                    state = "disabled"
                )
                self.popup_empty_submenu.entryconfig(
                    3,
                    state = "disabled"
                )

            # Only one SAS is allowed.
            # Hence, turn off the popup menu command if one is exists.
            if (isinstance(op, MOp_AddMemoryNode)
            and MemorySASNode.__name__ in op.nc
            ):
                state = "disabled"
                try:
                    mem = self.mach.id2node[op.node_id]
                except KeyError:
                    state = "normal"
                self.popup_empty_submenu.entryconfig(
                    4,
                    state = state
                )

        if isinstance(op, MOp_SetMemNodeAttr):
            mem = self.mach.id2node[op.node_id]
            val = getattr(mem, op.attr)

            self.item(str(mem.id),
                text = mem.name,
                values = (
                    mem.id,
                    hwaddr_val(mem.offset) if mem.parent else "--",
                    "--" if mem.size is None else hwaddr_val(mem.size),
                    memtype2str[type(mem)]
                )
            )

            if isinstance(mem, MemoryAliasNode):
                self.item(str(mem.alias_to.id) + "." + str(mem.id),
                    text = mem.alias_to.name,
                    values = ("", hwaddr_val(mem.alias_offset),)
                )

            if op.attr is "name":
                for n in self.mach.id2node.values():
                    if isinstance(n, MemoryAliasNode):
                        if n.alias_to is mem:
                            self.item(
                                str(n.alias_to.id) + "." + str(n.id),
                                text = val
                            )
        elif isinstance(op,
            (
                MOp_AddMemChild,
                MOp_RemoveMemChild,
                MOp_AddMemoryNode,
                MOp_DelMemoryNode,
                MOp_SetMemNodeAlias
            )
        ):
            l = self.gen_layout()
            self.delete(*self.get_children())
            self.iid2node.clear()
            self.widget_initialization()
            self.set_layout(l)

        if isinstance(op, MOp_AddMemChild):
            self.selected = self.mach.id2node[op.child_id]

        if self.selected:
            if self.selected.id in self.mach.id2node:
                self.on_select_origin()

    def show_memory_settings(self, mem, x, y):
        wnd = MemorySettingsWindow(mem, self.mach, self.mht, self)

        geom = "+" + str(int(self.winfo_rootx() + x)) \
             + "+" + str(int(self.winfo_rooty() + y))

        wnd.geometry(geom)

    def on_popup_node_settings(self):
        p = self.current_popup

        self.show_memory_settings(
            self.selected,
            p.winfo_rootx() - self.winfo_rootx(),
            p.winfo_rooty() - self.winfo_rooty()
        )

        self.notify_popup_command()

    def on_popup_node_alias_target(self):
        self.alias_to = self.selected

        self.popup_not_leaf_node_submenu.entryconfig(
            3,
            state = "normal"
        )
        self.popup_empty_submenu.entryconfig(
            3,
            state = "normal"
        )

        self.notify_popup_command()

    def on_popup_node_delete(self):
        self.mht.delete_memory_node(self.selected.id)
        self.mht.commit()

        self.notify_popup_command()

    def on_key_delete(self, event):
        prev_pos = self.mht.pos

        for node_id in [
            int(iid) for iid in self.selection() \
                if "." not in iid # skip pseudo nodes
        ]:
            if node_id in self.mach.id2node:
                # Deletion of a node may cause another node deletion.
                self.mht.delete_memory_node(node_id)

        if prev_pos != self.mht.pos:
            self.mht.commit(
                sequence_description = _("Deletion of selected memory nodes")
            )

    def add_memory_node_at_popup(self, class_name):
        node_id = self.mach.get_free_id()

        memory_arguments = {}

        if class_name == "MemoryAliasNode":
            memory_arguments = { "alias_to": self.alias_to, "offset": 0x0 }

        self.mht.add_memory_node(class_name, node_id, **memory_arguments)
        if self.selected:
            self.mht.stage(MOp_AddMemChild, node_id, self.selected.id)
        self.mht.commit()

        self.notify_popup_command()

    def on_add_container(self):
        self.add_memory_node_at_popup("MemoryNode")

    def on_add_sas(self):
        self.add_memory_node_at_popup("MemorySASNode")

    def on_add_ram(self):
        self.add_memory_node_at_popup("MemoryRAMNode")

    def on_add_rom(self):
        self.add_memory_node_at_popup("MemoryROMNode")

    def on_add_alias(self):
        self.add_memory_node_at_popup("MemoryAliasNode")

    def on_select_origin(self):
        self.selection_set(self.selected.id)
        self.focus(self.selected.id)
        self.see(self.selected.id)

    def widget_initialization(self):
        mems_queue = [m for m in self.mach.mems if not m.parent]
        unprocessed_mems = list(self.mach.mems)

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
                    if isinstance(m, MemoryLeafNode):
                        if m.parent and not self.exists(m.parent.id):
                            unprocessed_mems.append(m)
                            continue

                    parent_id = ""
                    if m.parent and self.exists(m.parent.id):
                        parent_id = m.parent.id

                    self.insert(parent_id, "end",
                        iid = str(m.id),
                        text = m.name,
                        values = (
                            m.id,
                            hwaddr_val(m.offset) if m.parent else "--",
                            "--" if m.size is None else hwaddr_val(m.size),
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

    def on_b3_press(self, event):
        iid = self.identify_row(event.y)
        """ When user clicks over a row, the row should be be selected
        in the tree view. This prevents confusion of row for which the popup
        is shown. """

        self.selection_set(iid)
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

    def on_b1_double(self, event):
        iid = self.identify_row(event.y)

        try:
            self.selected = self.iid2node[iid]
        except:
            if "." in iid:
                self.selected = self.iid2node[iid.split(".", 1)[0]]
            else:
                self.selected = None

        if self.selected:
            if (self.identify_element(event.x, event.y) == 'Treeitem.indicator'
            and self.get_children(iid)
            ):
                self.item(iid, open = not self.item(iid, "open"))
            else:
                self.show_memory_settings(self.selected, event.x, event.y)

        # print("on_b1_double")

        return "break"

    def on_b1_release(self, event):
        self.unbind("<ButtonRelease-1>")

        dragged = self.dragged_iid

        iid = self.identify_row(event.y)
        old_placed = False
        if "-place" in iid:
            new_parent = self.parent(iid)
            self.reattach(dragged, new_parent, self.index(iid))

            try:
                new_parent_id = int(new_parent)
            except ValueError:
                new_parent_id = -1

            try:
                cur_parent_id = int(self.old_parent)
            except ValueError:
                cur_parent_id = -1

            if not new_parent_id == cur_parent_id:
                mem_id = int(dragged)
                if not cur_parent_id == -1:
                    self.mht.stage(MOp_RemoveMemChild, mem_id, cur_parent_id)
                if not new_parent_id == -1:
                    self.mht.stage(MOp_AddMemChild, mem_id, new_parent_id)

            mem = self.iid2node[dragged]
            self.mht.commit(sequence_description =
                _("Moving of memory '%s' (%d).") % (
                    mem.name, mem.id
                )
            )
        else:
            old_placed = True

        while self.highlighted_path:
            p = self.highlighted_path.pop()
            if self.exists(p + "-up-place"):
                self.delete(p + "-up-place")
            if self.exists(p + "-down-place"):
                self.delete(p + "-down-place")

        if self.exists("child-place"):
            self.delete("child-place")

        self.dragged_label.hide()

        if old_placed:
            self.reattach(dragged, self.old_parent, self.old_index)

        self.see(dragged)
        self.focus(dragged)
        self.selection_set(dragged)

        self.dragged_iid = None
        self.sas_dnd =  False
        self.enable_hotkeys()

    def on_b1_move(self, event):
        if not self.dragged_iid:
            iid = self.identify_row(event.y)

            if ("." in iid # skip pseudo nodes
            or iid == ""   # skip empty place
            ):
                return

            self.disable_hotkeys()

            self.dragged_iid = iid
            self.sas_dnd = type(self.iid2node[iid]) is MemorySASNode
            self.old_parent = self.parent(iid)
            self.old_index = self.index(iid)

            self.dragged_label.set_text(self.item(iid)["text"])
            self.dragged_label.show(event)

            self.detach(iid)
            self.selection_remove(self.selection())
            self.focus(None)

            self.bind("<ButtonRelease-1>", self.on_b1_release)

        self.dragged_label.move(event)

        iid = self.identify_row(event.y)
        self.focus(iid)
        self.selection_set(iid)

        highlighted_path = self.highlighted_path

        # start moving from empty place
        if iid == "" and not highlighted_path:
            try:
                iid = self.get_children()[-1]
            except IndexError:
                pass

        if (iid == ""
        or "." in iid and ".loop" not in iid
        or "-place" in iid
        or highlighted_path and highlighted_path[-1] == iid
        or self.sas_dnd and self.parent(iid) != ""
        ):
            return

        highlighted_path_cur = []
        cur_iid = iid
        while cur_iid != "":
            highlighted_path_cur.append(cur_iid)
            cur_iid = self.parent(cur_iid)
        highlighted_path_cur.reverse()

        diff = 0
        for diff, (old, new) in enumerate(
        zip(highlighted_path, highlighted_path_cur)
        ):
            if old != new:
                break

        for p in highlighted_path[diff:]:
            if self.exists(p + "-up-place"):
                self.delete(p + "-up-place")
            if self.exists(p + "-down-place"):
                self.delete(p + "-down-place")

        if self.exists("child-place"):
            self.delete("child-place")

        for p in highlighted_path_cur[diff:]:
            par = self.parent(p)
            ind = self.index(p)

            self.insert(par, ind + 1,
                iid = p + "-down-place",
                text = "HERE",
                tags = ("places")
            )

        if highlighted_path_cur:
            p = highlighted_path_cur[-1]
            par = self.parent(p)
            ind = self.index(p)

            self.insert(par, ind,
                iid = p + "-up-place",
                text = "HERE",
                tags = ("places")
            )
            self.see(p + "-up-place")

            if (not self.sas_dnd
            and "." not in p
            and type(self.iid2node[p]) is MemoryNode
            ):
                self.insert(p, 0,
                    iid = "child-place",
                    text = "HERE",
                    tags = ("places")
                )
                self.see("child-place")

        self.highlighted_path = highlighted_path_cur

    def gen_layout(self):
        layout = {}

        if not self.get_children():
            return layout

        for m in self.mach.mems:
            try:
                val = bool(self.item(str(m.id), "open"))
            except TclError:
                pass
            else:
                if val:
                    layout[m.id] = val

        cols_width = {}
        for col in ("#0",) + self.cget("columns"):
            cols_width[col] = self.column(col, "width")

        layout[-1] = { LAYOUT_COLUMNS_WIDTH : cols_width }

        return layout

    def set_layout(self, l):
        layout_bak = self.gen_layout()
        try:
            for id, desc in l.items():
                if id == -1:
                    try:
                        cols_width = desc[LAYOUT_COLUMNS_WIDTH]
                    except KeyError:
                        continue

                    for col, col_width in cols_width.items():
                        self.column(col, width = col_width)

                elif id in self.mach.id2node:
                    self.item(str(id), open = desc)
        except:
            # if new layout is incorrect then restore previous one
            self.set_layout(layout_bak)

