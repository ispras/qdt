from var_widgets import \
    VarLabel, \
    VarButton, \
    VarLabelFrame, \
    VarCheckbutton, \
    VarToplevel

from common import \
    ML as _

import Tkinter as tk

import qemu

from qemu import \
    MachineDeviceOperation, \
        MOp_DelDevProp, \
        MOp_AddDevProp, \
        MOp_SetDevProp

class PropLineDesc(object):
    def __init__(self, device_settings_widget, prop):
        self.dsw = device_settings_widget
        self.prop = prop

    def on_delete(self):
        del self.dsw.prop2field[self.prop]

        self.e_name.destroy()
        self.om_type.destroy()
        self.w_val.destroy()
        self.bt_del.destroy()

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

        if not new_type == self.prop.prop_type:
            self.w_val.destroy()

            # fixme: assign a default value for each type
            new_val = None

            w_p_val, var_p_val = self.gen_prop_value_widget(new_type, new_val)
            w_p_val.grid(
                column = 2,
                row = self.row,
                sticky = "NEWS"
            )

            self.w_val = w_p_val
            self.v_val = var_p_val

    def gen_prop_value_widget(self, prop_type, prop_val):
        if prop_type == qemu.QOMPropertyTypeLink:
            var = tk.StringVar()
            keys = ["-1: NULL"]
            #todo: get list of machinde devices
            if prop_val:
                keys.append(
                    DeviceSettingsWidget.gen_node_link_text(prop_val))

            ret = tk.OptionMenu(self.dsw.props_lf, var, *keys)
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
        self.v_val = var_p_val
        self.bt_del = bt_del

class DeviceSettingsWidget(tk.Frame):
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

    def __init__(self,
            master,
            device,
            machine_history_tracker,
            *args, **kwargs
        ):
        tk.Frame.__init__(self, master,  *args, **kwargs)
        self.dev = device
        self.mht = machine_history_tracker

        self.grid()

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

        self.rowconfigure(1, weight = 1)

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

        self.refresh()

        self.mht.add_on_changed(self.on_changed)

    def destroy(self):
        self.mht.remove_on_changed(self.on_changed)
        tk.Frame.destroy(self)

    def on_changed(self, op, *args, **kw):
        if not isinstance(op, MachineDeviceOperation):
            return
        if not op.dev_id == self.dev.id:
            return

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

        for row, p in enumerate(self.dev.properties):
            lpd = PropLineDesc(self, p)
            lpd.gen_row(row)
            # Do not use different QOMPropertyValue as the key for the
            # PropLineDesc of corresponding device-stored QOMPropertyValue
            # The QOMPropertyValue is used to apply deletion of device
            # property. 
            self.prop2field[p] = lpd

    def apply(self):
        self.mht.remove_on_changed(self.on_changed)

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
                raise Exception("Adding device properties is no implemented.")
                # self.mht.stage(MOp_AddDevProp, p, self.dev.id)

        for p in self.dev.properties:
            if not p in self.prop2field:
                self.mht.stage(MOp_DelDevProp, p, self.dev.id)

        self.mht.commit()

        self.mht.add_on_changed(self.on_changed)

class DeviceSettingsWindow(VarToplevel):
    def __init__(self,
            master,
            device,
            machine_history_tracker,
            *args, **kwargs
        ):
        VarToplevel.__init__(self, master, *args, **kwargs)

        self.title(_("Device settings"))

        self.grid()
        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 1)

        self.dsw = DeviceSettingsWidget(self, device, machine_history_tracker)
        self.dsw.grid(
            row = 0,
            column = 0,
            sticky = "NEWS"
        )

        self.rowconfigure(1, weight = 0)

        fr = tk.Frame(self)
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
            command = self.dsw.refresh
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

    def apply(self):
        self.dsw.apply()
        self.dsw.refresh()

    def apply_and_quit(self):
        self.dsw.apply()
        self.destroy()
