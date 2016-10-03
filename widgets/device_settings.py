from var_widgets import \
    VarLabel, \
    VarButton, \
    VarLabelFrame, \
    VarCheckbutton

from device_tree_widget import \
    DeviceTreeWidget

from common import \
    ML as _

import Tkinter as tk
import ttk

import qemu

from qemu import \
    MOp_SetChildBus, \
    MachineNodeOperation, \
        MOp_SetDevParentBus, \
        MOp_SetDevQOMType, \
        MOp_DelDevProp, \
        MOp_AddDevProp, \
        MOp_SetDevProp

from itertools import \
    izip, \
    count

from settings_window import \
    SettingsWidget

class BusLineDesc(object):
    def __init__(self, device_settings_widget, idx):
        self.dsw = device_settings_widget
        self.idx = idx

    def gen_row(self):
        p = self.dsw.buses_lf

        p.rowconfigure(self.idx, weight = 1)

        self.v = tk.StringVar()
        # When a bus is selected all Combobox values lists should be updated
        # to prevent selecting of this bus in another Combobox
        self._on_var_changed = self.v.trace_variable("w", self.on_var_changed)

        self.cb = ttk.Combobox(p,
            textvariable = self.v,
            state = "readonly"
        )
        self.cb.grid(row = self.idx, column = 0, sticky = "NEWS")

        self._on_bus_selected = self.dsw.bind(
            DeviceSettingsWidget.EVENT_BUS_SELECTED, self.on_bus_selected, "+")

    def on_var_changed(self, *args):
        self.dsw.event_generate(DeviceSettingsWidget.EVENT_BUS_SELECTED)

    def update(self):
        try:
            cur_bus = self.dsw.dev.buses[self.idx]
        except IndexError:
            cur_bus = None
        bus_text = DeviceSettingsWidget.gen_node_link_text(cur_bus)

        self.v.set(bus_text)

    def delete(self):
        self.v.trace_vdelete("w", self._on_var_changed)

        self.dsw.unbind(DeviceSettingsWidget.EVENT_BUS_SELECTED,
            self._on_bus_selected)

        if "obs" in self.__dict__:
            self.v.trace_vdelete("w", self.obs)
            del self.obs

        self.cb.destroy()

    def update_values(self):
        sel_buses = self.dsw.get_selected_buses()

        values = [
            DeviceSettingsWidget.gen_node_link_text(b) for b in (
                [ b for b in self.dsw.mht.mach.buses if (\
                        (   b.parent_device is None \
                         or b.parent_device == self.dsw.dev) 
                    and (not b.id in sel_buses))
                ] + [ None ]
            )
        ]

        self.cb.config(values = values)

    def on_bus_selected(self, event):
        self.update_values()

    def on_dsw_destroy(self, event):
        self.delete()

class PropLineDesc(object):
    def __init__(self, device_settings_widget, prop):
        self.dsw = device_settings_widget
        self.prop = prop
        # It stores property type for which the value widget was generated.
        self.val_widget_prop_type = None

    def on_delete(self):
        del self.dsw.prop2field[self.prop]

        self.e_name.destroy()
        self.om_type.destroy()
        self.w_val.destroy()
        self.bt_del.destroy()

        for pld in self.dsw.prop2field.values():
            if pld.row > self.row:
                row = pld.row - 1
                pld.row = row

                pld.e_name.grid(row = row)
                pld.om_type.grid(row = row)
                pld.w_val.grid(row = row)
                pld.bt_del.grid(row = row)

        # TODO: the Add button is to be shifted too.

    def get_current_type(self):
        type_name = self.v_type.get()
        return DeviceSettingsWidget.prop_name_type_map[type_name]

    def get_current_val(self):
        prop_type = self.get_current_type()
        if prop_type == qemu.QOMPropertyTypeLink:
            link_text = self.v_val.get()
            ret = self.dsw.find_node_by_link_text(link_text)
        elif prop_type == qemu.QOMPropertyTypeBoolean:
            ret = self.v_val.get()
        elif prop_type == qemu.QOMPropertyTypeInteger:
            long_text = self.v_val.get()
            ret = long(long_text, base = 0)
        elif prop_type == qemu.QOMPropertyTypeString:
            ret = str(self.v_val.get())
        else:
            raise Exception("Unknown property type")
        return ret

    def get_current_name(self):
        return self.v_name.get()

    def on_prop_type_changed(self, *args):
        new_type = self.get_current_type()

        if not new_type == self.val_widget_prop_type:
            self.w_val.destroy()

            if new_type == self.prop.prop_type:
                new_val = self.prop.prop_val
            else:
                # fixme: assign a default value for each type
                new_val = None

            w_p_val, var_p_val = self.gen_prop_value_widget(new_type, new_val)
            w_p_val.grid(
                column = 2,
                row = self.row,
                sticky = "NEWS"
            )

            self.val_widget_prop_type = new_type
            self.w_val = w_p_val
            self.v_val = var_p_val

    def gen_prop_value_widget(self, prop_type, prop_val):
        if prop_type == qemu.QOMPropertyTypeLink:
            var = tk.StringVar()
            keys = [ DeviceSettingsWidget.gen_node_link_text(n) \
                    for n in [ None ] + self.dsw.mht.mach.id2node.values()
                   ]

            ret = ttk.Combobox(self.dsw.props_lf, 
                textvariable = var,
                values = keys,
                state = "readonly"
            )
            if prop_val:
                current = DeviceSettingsWidget.gen_node_link_text(prop_val)
            else:
                current = keys[0]

            var.set(current)
        elif prop_type == qemu.QOMPropertyTypeBoolean:
            var = tk.BooleanVar()
            ret = VarCheckbutton(
                self.dsw.props_lf,
                text = tk.StringVar(""),
                variable = var
            )
            if prop_val is None:
                current = False
            else:
                current = bool(prop_val)

            var.set(current)
        else:
            var = tk.StringVar()
            ret = tk.Entry(
                self.dsw.props_lf,
                textvariable = var
            )

            if prop_val:
                if prop_type == qemu.QOMPropertyTypeInteger:
                    current = prop_type.build_val(prop_val)
                else:
                    current = str(prop_val)
            else:
                if prop_type == qemu.QOMPropertyTypeInteger:
                    current = "0x0"
                else:
                    current = ""

            var.set(current)

        return ret, var

    def gen_row(self, row):
        var_p_name = tk.StringVar()
        var_p_name.set(self.prop.prop_name)
        e_p_name = tk.Entry(self.dsw.props_lf, textvariable = var_p_name)
        e_p_name.grid(
            column = 0,
            row = row,
            sticky = "NEWS"
        )

        om_p_type, var_p_type  = DeviceSettingsWidget.gen_prop_type_optionmenu(
            self.dsw.props_lf,
            self.prop.prop_type
        )
        om_p_type.grid(
            column = 1,
            row = row,
            sticky = "NEWS"
        )
        var_p_type.trace_variable("w", self.on_prop_type_changed)

        w_p_val, var_p_val = self.gen_prop_value_widget(
            self.prop.prop_type,
            self.prop.prop_val 
        )
        w_p_val.grid(
            column = 2,
            row = row,
            sticky = "NEWS"
        )

        bt_del = VarButton(
            self.dsw.props_lf,
            text = _("Delete"),
            command = self.on_delete
        )
        bt_del.grid(
            column = 3,
            row = row,
            sticky = "NEWS"
        )

        self.row = row
        self.e_name = e_p_name
        self.v_name = var_p_name
        self.om_type = om_p_type
        self.v_type = var_p_type
        self.w_val = w_p_val
        self.val_widget_prop_type = self.prop.prop_type
        self.v_val = var_p_val
        self.bt_del = bt_del

class DeviceSettingsWidget(SettingsWidget):
    EVENT_BUS_SELECTED = "<<DSWBusSelected>>"

    prop_type_name_map = {
        qemu.QOMPropertyTypeInteger: ("Integer", ),
        qemu.QOMPropertyTypeLink: ("Link", ),
        qemu.QOMPropertyTypeString: ("String", ),
        qemu.QOMPropertyTypeBoolean: ("Boolean", )
    }
    prop_name_type_map = {
        "Integer": qemu.QOMPropertyTypeInteger,
        "Link": qemu.QOMPropertyTypeLink,
        "String": qemu.QOMPropertyTypeString,
        "Boolean": qemu.QOMPropertyTypeBoolean
    }

    def __init__(self, device, *args, **kw):
        SettingsWidget.__init__(self, *args, **kw)
        self.dev = device

        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 0)
        common_fr = tk.Frame(self)
        common_fr.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )
        common_fr.columnconfigure(0, weight = 0)
        common_fr.columnconfigure(1, weight = 1)

        common_fr.rowconfigure(0, weight = 0)

        l = VarLabel(common_fr, text = _("QOM type"))
        self.qom_type_var = tk.StringVar()
        e = tk.Entry(common_fr, textvariable = self.qom_type_var)

        l.grid(row = 0, column = 0, sticky = "W")
        e.grid(row = 0, column = 1, sticky = "EW")

        b = VarButton(common_fr,
            text = _("Select"),
            command = self.on_press_select_qom_type
        )
        b.grid(row = 0, column = 2, sticky = "EW")

        # parent bus editing widgets
        l = VarLabel(common_fr, text = _("Parent bus"))
        self.bus_var = tk.StringVar()
        self.bus_var.trace_variable("w", self.on_parent_bus_var_changed)
        self.bus_cb = ttk.Combobox(
            common_fr,
            textvariable = self.bus_var,
            state = "readonly"
        )

        l.grid(row = 1, column = 0, sticky = "W")
        self.bus_cb.grid(row = 1, column = 1, sticky = "EW")
        common_fr.rowconfigure(1, weight = 0)

        self.rowconfigure(1, weight = 1)

        self.buses_lf = lf = VarLabelFrame(
            common_fr,
            text = _("Child buses")
        )
        lf.grid(row = 2, column = 0, columns = 3, sticky = "NEWS")
        self.rowconfigure(2, weight = 1)

        lf.columnconfigure(0, weight = 1)

        self.child_buses_rows = []

        self.props_lf = VarLabelFrame(
            self,
            text = _("Properties")
        )
        self.props_lf.grid(
            row = 1,
            column = 0,
            sticky = "NEWS"
        )
        self.props_lf.columnconfigure(0, weight = 1)
        self.props_lf.columnconfigure(1, weight = 0)
        self.props_lf.columnconfigure(2, weight = 1)
        self.props_lf.columnconfigure(3, weight = 0)
        self.prop2field = {}

        self.bt_add_prop = VarButton(
            self.props_lf,
            text = _("Add"),
            command = self.on_prop_add
        )
        self.bt_add_prop.grid(
            column = 3,
            sticky = "NEWS"
        )

    def __on_destroy__(self, *args):
        for bld in self.child_buses_rows:
            bld.delete()

        SettingsWidget.__on_destroy__(self, *args)

    def on_parent_bus_var_changed(self, *args):
        self.event_generate(DeviceSettingsWidget.EVENT_BUS_SELECTED)

    def on_press_select_qom_type(self):
        DeviceTreeWidget(self)

    def gen_uniq_prop_name(self):
        for x in count(0, 1):
            name = "name-of-new-property-" + str(x)
            for prop in self.prop2field:
                if name == prop.prop_name:
                    name = None
                    break
            if name:
                return name

    def on_prop_add(self):
        p = qemu.QOMPropertyValue(
            qemu.QOMPropertyTypeLink,
            self.gen_uniq_prop_name(),
            None
        )
        lpd = PropLineDesc(self, p)
        row = len(self.prop2field)
        lpd.gen_row(row)

        self.prop2field[p] = lpd

        # Move add button bottom
        self.bt_add_prop.grid(row = row + 1)

    def on_changed(self, op, *args, **kw):
        if isinstance(op, MOp_SetChildBus):
            self.event_generate(DeviceSettingsWidget.EVENT_BUS_SELECTED)

        if isinstance(op, MOp_SetDevParentBus):
            self.event_generate(DeviceSettingsWidget.EVENT_BUS_SELECTED)

        if op.writes(self.dev.id):
            if not self.dev.id in self.mht.mach.id2node:
                self.destroy()
            else:
                self.refresh()
        elif isinstance(op, MachineNodeOperation) \
        and (op.node_id == self.dev.id):
            self.refresh()

    @staticmethod
    def gen_prop_type_optionmenu(parent, current = None):
        var = tk.StringVar()
        keys = []
        for ptn in DeviceSettingsWidget.prop_type_name_map.values():
            keys.append(ptn[0])

        om = tk.OptionMenu(parent, var, *keys)

        if current:
            current = DeviceSettingsWidget.prop_type_name_map[current][0]
        else:
            DeviceSettingsWidget.prop_type_name_map.values()[0]

        var.set(current)

        return om, var

    @staticmethod
    def gen_node_link_text(node):
        # TODO: localize?
        if node is None:
            return "-1: NULL"

        ret = str(node.id) + ": "
        if isinstance(node, qemu.BusNode):
            ret = ret + "Bus, " + node.gen_child_name_for_bus()
        elif isinstance(node, qemu.IRQLine):
            ret = ret + "IRQ: " \
                + DeviceSettingsWidget.gen_node_link_text(node.src[0]) \
                + " -> " \
                + DeviceSettingsWidget.gen_node_link_text(node.dst[0])
        elif isinstance(node, qemu.IRQHub):
            ret = ret + "IRQ Hub"
        elif isinstance(node, qemu.DeviceNode):
            ret = ret + "Device, " + node.qom_type
        elif isinstance(node, qemu.MemoryNode):
            ret = ret + "Memory, " + node.name

        return ret

    def find_node_by_link_text(self, text):
        id = text.split(":")[0]
        id = int(id)
        if id < 0:
            return None
        else:
            return self.mht.mach.id2node[id]

    def refresh(self):
        self.qom_type_var.set(self.dev.qom_type)

        for p, desc in self.prop2field.iteritems():
            desc.e_name.destroy()
            desc.om_type.destroy()
            desc.w_val.destroy()
            desc.bt_del.destroy()

        self.prop2field = {}

        # If self.dev.properties is empty the row variable will remain
        # undefined.
        row = -1
        for row, p in enumerate(self.dev.properties):
            lpd = PropLineDesc(self, p)
            lpd.gen_row(row)
            # Do not use different QOMPropertyValue as the key for the
            # PropLineDesc of corresponding device-stored QOMPropertyValue
            # The QOMPropertyValue is used to apply deletion of device
            # property. 
            self.prop2field[p] = lpd

        self.bt_add_prop.grid(row = row + 1)

        # refresh parent bus
        buses = [ DeviceSettingsWidget.gen_node_link_text(None) ]
        for n in self.mht.mach.id2node.values():
            if not isinstance(n, qemu.BusNode):
                continue
            buses.append(DeviceSettingsWidget.gen_node_link_text(n))
        self.bus_cb.config(values = buses)
        self.bus_var.set(
            DeviceSettingsWidget.gen_node_link_text(self.dev.parent_bus)
        )

        bus_row_count = len(self.child_buses_rows)
        bus_count = len(self.dev.buses) + 1

        if bus_row_count < bus_count:
            for idx in xrange(bus_row_count, bus_count):
                bld = BusLineDesc(self, idx)
                self.child_buses_rows.append(bld)
                bld.gen_row()

            bld.obs = bld.v.trace_variable("w", self.on_last_child_bus_changed)

        if bus_count < bus_row_count:
            for idx in xrange(bus_count, bus_row_count):
                bld = self.child_buses_rows.pop()
                bld.delete()

            bld = self.child_buses_rows[-1]
            bld.obs = bld.v.trace_variable("w", 
                self.on_last_child_bus_changed)

        for bld in self.child_buses_rows:
            bld.update()

    def on_last_child_bus_changed(self, *args):
        bld = self.child_buses_rows[-1]
        bus = self.find_node_by_link_text(bld.v.get())

        if not bus is None:
            # Selecting not NULL child bus means that a child bus was added.
            # Add new NULL bus string for consequent bus addition.
            bld.v.trace_vdelete("w", bld.obs)
            del bld.obs

            bld = BusLineDesc(self, len(self.child_buses_rows))
            self.child_buses_rows.append(bld)
            bld.gen_row()
            bld.update()

            bld.obs = bld.v.trace_variable("w", self.on_last_child_bus_changed)

    def get_selected_child_buses(self):
        child_buses = [ bld.v.get() for bld in self.child_buses_rows ]
        ret = [ self.find_node_by_link_text(t) for t in child_buses if t ]
        return [ b.id for b in ret if not b is None ]

    def get_selected_buses(self):
        ret = self.get_selected_child_buses()

        parent_bus = self.find_node_by_link_text(self.bus_var.get())
        if not parent_bus is None:
            parent_bus = parent_bus.id
            if not parent_bus in ret:
                ret.append(parent_bus)

        return ret

    def __apply_internal__(self):
        # apply parent bus
        new_bus_text = self.bus_var.get()
        new_bus = self.find_node_by_link_text(new_bus_text)
        if not self.dev.parent_bus == new_bus:
            self.mht.stage(MOp_SetDevParentBus, new_bus, self.dev.id)

        qom = self.qom_type_var.get()
        if not self.dev.qom_type == qom:
            self.mht.stage(MOp_SetDevQOMType, qom, self.dev.id)

        for p, desc in self.prop2field.iteritems():
            cur_name, cur_type, cur_val = desc.get_current_name(), \
                desc.get_current_type(), desc.get_current_val()

            try:
                dev_p = self.dev.properties[cur_name]
                if not (
                        dev_p.prop_type == cur_type 
                    and dev_p.prop_val == cur_val
                ):
                    self.mht.stage(
                        MOp_SetDevProp,
                        cur_type,
                        cur_val,
                        dev_p,
                        self.dev.id
                    )
            except KeyError:
                self.mht.stage(MOp_AddDevProp, p, self.dev.id)

        for p in self.dev.properties:
            if not p in self.prop2field:
                self.mht.stage(MOp_DelDevProp, p, self.dev.id)

        new_buses = self.get_selected_child_buses()

        # Changing of buses is made in two steps to allow reordering of buses
        # during single iteration.
        step2 = []

        # The child bus list is reversed to remove buses from the end to to the
        # begin. After removing bus from middle consequent indexes becomes
        # incorrect.
        for i, bus in reversed([ x for x in enumerate(self.dev.buses) ]):
            try:
                new_bus = new_buses.pop(i)
            except IndexError:
                # remove i-th bus
                self.mht.stage(
                    MOp_SetChildBus,
                    self.dev.id,
                    i,
                    -1
                )
            else:
                if bus.id == new_bus:
                    continue

                # change i-th bus (1-st step: remove)
                self.mht.stage(
                    MOp_SetChildBus,
                    self.dev.id,
                    i,
                    -1
                )
                # step 2 should be done in increasing index order
                step2.insert(0, (i, new_bus))

        adding = [ x for x in izip(count(len(self.dev.buses)), new_buses) ]

        for i, new_bus in step2 + adding:
            # add i-th bus
            self.mht.stage(
                MOp_SetChildBus,
                self.dev.id,
                i,
                new_bus
            )
