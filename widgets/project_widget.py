from var_widgets import \
    VarMenu, \
    VarTreeview

from close_button_notebook import \
    CloseButtonNotebook

from machine_widget import \
    MachineDescriptionSettingsWidget

from qemu import \
    SysBusDeviceDescription, \
    PCIExpressDeviceDescription, \
    MachineNode

from Tkinter import \
    NO, \
    PanedWindow

from common import \
    CoTask, \
    mlget as _

from qemu import \
    qvd_get, \
    qvd_load_with_cache, \
    DOp_SetAttr, \
    POp_AddDesc

from sysbusdev_description_settings import \
    SystemBusDeviceDescriptionSettingsWidget

from pci_description_settings import \
    PCIEBusDeviceDescriptionSettingsWidget

from tkFont import \
    Font

from gui_frame import \
    GUIFrame

from ttk import \
    Scrollbar

from add_desc_dialog import \
    AddDescriptionDialog

from gui_editing import \
    POp_SetDescLayout

from popup_helper import \
    TkPopupHelper

class ReloadBuildPathTask(CoTask):
    def __init__(self, project_widget):
        self.pht = project_widget.pht
        self.qvd = qvd_get(project_widget.p.build_path)
        CoTask.__init__(self, generator = self.qvd.co_init_cache())

    def on_finished(self):
        self.qvd.use()
        if self.pht is not None:
            self.pht.all_pci_ids_2_objects()

class DescriptionsTreeview(VarTreeview):
    def __init__(self, descriptions, *args, **kw):
        kw["columns"] = [
            "directory"
        ]

        VarTreeview.__init__(self, *args, **kw)

        self.descs = descriptions

        ml_text = _("Name")
        self.heading("#0", text = ml_text)
        ml_text.trace_variable("w", self.on_column_heading_changed)

        ml_text = _("Directory")
        self.heading("directory", text = ml_text)
        ml_text.trace_variable("w", self.on_column_heading_changed)

        self.column("#0", stretch = NO)
        self.column("directory", stretch = NO)

        self.after(0, self.update)

    def on_column_heading_changed(self, *args):
        self.adjust_widths()

    def adjust_widths(self):
        f = Font()

        max_name_len = f.measure(self.heading("#0")["text"])
        max_dir_len = f.measure(self.heading("directory")["text"])

        for d in self.descs:
            l = f.measure(d.name)
            if l > max_name_len:
                max_name_len = l

            l = f.measure(d.directory)
            if l > max_dir_len:
                max_dir_len = l

            self.column("#0", width = max_name_len)
            self.column("directory", width = max_dir_len)

    def update(self):
        self.delete(*self.get_children())

        for i, d in enumerate(self.descs):
            self.insert('', i, text = d.name, values = [d.directory])

        self.adjust_widths()

class ProjectWidget(PanedWindow, TkPopupHelper):
    def __init__(self, project, *args, **kw):
        PanedWindow.__init__(self, *args, **kw)
        TkPopupHelper.__init__(self)

        self.p = project

        try:
            self.pht = self.winfo_toplevel().pht
        except AttributeError:
            self.pht = None

        # snapshot mode without PHT
        if self.pht is not None:
            self.pht.add_on_changed(self.on_project_changed)

        try:
            self.tm = self.winfo_toplevel().task_manager
        except AttributeError:
            self.tm = None

        fr = GUIFrame(self)
        fr.grid()
        fr.rowconfigure(0, weight = 1)
        fr.rowconfigure(1, weight = 0)
        fr.columnconfigure(0, weight = 1)
        fr.columnconfigure(1, weight = 0)

        tv = self.tv_descs = DescriptionsTreeview(self.p.descriptions, fr)
        tv.grid(row = 0, column = 0, sticky = "NEWS")

        vsb = Scrollbar(fr, orient="vertical", command = tv.yview)
        vsb.grid(row = 0, column = 1, sticky = "NS")

        hsb = Scrollbar(fr, orient="horizontal", command = tv.xview)
        hsb.grid(row = 1, column = 0, sticky = "EW")

        tv.configure(yscrollcommand = vsb.set, xscrollcommand = hsb.set)

        self.add(fr)

        self.nb_descriptions = CloseButtonNotebook(self)
        self.add(self.nb_descriptions)

        tvm = VarMenu(self.winfo_toplevel(), tearoff = False)
        tvm.add_command(
            label = _("Add description"),
            command = self.on_add_description
        )

        self.popup_tv_empty = tvm

        tvm = VarMenu(self.winfo_toplevel(), tearoff = False)
        tvm.add_command(
            label = _("Delete description"),
            command = self.notify_popup_command if self.pht is None \
                else self.on_delete_description
        )

        self.popup_tv_single = tvm

        for desc_name, lys in self.p.layouts.iteritems():
            for l in lys.values():
                if not l.shown:
                    continue

                if l.widget is None:
                    desc = self.p.find(name = desc_name).next()

                    w = self.gen_widget(desc)
                    try:
                        w.set_layout(l.opaque)
                    except:
                        w.destroy()
                        w = None
                        l.shown = False
                    else:
                        l.widget = w

                        self.nb_descriptions.add(w, text = desc.name)

        self.tv_descs.bind("<Double-1>", self.on_tv_desc_b1_double)

        self.tv_descs.bind("<Button-3>", self.on_tv_b3, "+")

        self.nb_descriptions.bind("<<NotebookTabClosed>>",
            self.on_notebook_tab_closed)

        self.__account_build_path = self.after(1, self.account_build_path)

        self.bind("<Destroy>", self.__on_destroy__, "+")

    def __on_destroy__(self, event):
        if self.pht is not None:
            self.pht.remove_on_changed(self.on_project_changed)

        try:
            self.after_cancel(self.__account_build_path)
        except AttributeError:
            pass

        try:
            self.tm.remove(self.reload_build_path_task)
        except AttributeError:
            pass

    def on_tv_b3(self, event):
        # select appropriate menu
        popup = self.popup_tv_empty

        row = self.tv_descs.identify_row(event.y)

        if row != "":
            self.tv_descs.selection_set(row)
            popup = self.popup_tv_single

        self.show_popup(event.x_root, event.y_root, popup, row)

    def on_add_description(self):
        self.add_description()

        self.notify_popup_command()

    def on_delete_description(self):
        item = self.tv_descs.selection()[0]
        name = self.tv_descs.item(item)["text"]
        desc = self.p.find(name = name).next()
        self.refresh_layouts()
        self.pht.stage(POp_SetDescLayout, None, desc)
        self.pht.delete_description(desc)
        self.pht.commit()

        self.notify_popup_command()

    def account_build_path(self):
        del self.__account_build_path

        self.pht.all_pci_ids_2_values()

        if self.p.build_path is None:
            return

        if self.tm:
            # If task manager is available then use background task
            try:
                self.tm.remove(self.reload_build_path_task)
            except AttributeError:
                pass

            self.reload_build_path_task = ReloadBuildPathTask(self)
            self.tm.enqueue(self.reload_build_path_task)
        else:
            """ If no task manager is available then account build path right
            now. It will cause GUI to freeze but there are no more options. """

            qvd = qvd_load_with_cache(self.p.build_path)
            qvd.use()
            self.pht.all_pci_ids_2_objects()

    def on_project_changed(self, op):
        if isinstance(op, POp_AddDesc):
            self.tv_descs.update()

            for desc_name, lys in self.p.layouts.iteritems():
                try:
                    self.p.find(name = desc_name).next()
                except StopIteration:
                    # removed
                    for l in lys.values():
                        if l.widget is not None:
                            l.widget.destroy()
                            l.widget = None
                            l.shown = False
                    break
        elif isinstance(op, DOp_SetAttr):
            self.tv_descs.update()
        elif isinstance(op, POp_SetDescLayout):
            # remove all tabs that are not cached in current layouts
            for tab_id in self.nb_descriptions.tabs():
                desc_name = self.nb_descriptions.tab(tab_id)["text"]
                lys = self.p.get_layout_objects(desc_name)
                w = self.nametowidget(tab_id)
                for l in lys:
                    if l.widget is w:
                        break
                else:
                    w.destroy()


    def on_notebook_tab_closed(self, event):
        tabs = [ self.nametowidget(w) for w in self.nb_descriptions.tabs() ]
        for lys in self.p.layouts.values():
            for l in lys.values():
                if l.widget is not None and l.widget not in tabs:
                    l.widget.destroy()
                    l.widget = None
                    l.shown = False

                    break
            else:
                continue
            break

    def on_tv_desc_b1_double(self, event):
        try:
            item = self.tv_descs.selection()[0]
        except IndexError:
            # nothing is selected
            return

        name = self.tv_descs.item(item)["text"]

        for desc in self.p.descriptions:
            if desc.name == name:
                break

        layouts = sorted(
            self.p.get_layout_objects(desc.name),
            key = lambda l : l.lid
        )
        widgets = [ l.widget for l in layouts if l.widget is not None ]

        if not widgets:
            w = self.gen_widget(desc)

            for l in layouts:
                try:
                    w.set_layout(l.opaque)
                except:
                    continue
                else:
                    l.widget = w
                    break
            else:
                l = self.p.add_layout(desc.name, w.gen_layout())

            l.shown = True

            self.nb_descriptions.add(w, text = desc.name)
            for tab_id in self.nb_descriptions.tabs():
                if self.nb_descriptions.tab(tab_id)["text"] == desc.name:
                    break
            self.nb_descriptions.select(tab_id)
        else:
            # select next widget in layout id order
            tab_id = self.nb_descriptions.select()
            w = self.nametowidget(tab_id)
            if w in widgets:
                i = widgets.index(w)
                next_w = widgets[(i + 1) % len(widgets)]
            else:
                next_w = widgets[0]
            self.nb_descriptions.select(next_w)

    def refresh_layouts(self):
        for desc_layouts in self.p.layouts.values():
            for l in desc_layouts.values():
                l.sync_from_widget()
                """ "shown" from opaque dictionary is not more relevant while
                its attribute analog is maintained dynamically. """

    def gen_widget(self, desc):
        if isinstance(desc, MachineNode):
            w = MachineDescriptionSettingsWidget(desc, self)
        elif isinstance(desc, SysBusDeviceDescription):
            w = SystemBusDeviceDescriptionSettingsWidget(desc, self)
        elif isinstance(desc, PCIExpressDeviceDescription):
            w = PCIEBusDeviceDescriptionSettingsWidget(desc, self)
        else:
            raise Exception("No widget exists for description %s of type %s." %
                    (desc.name, type(desc).__name__)
                )
        return w

    def add_description(self):
        AddDescriptionDialog(self.pht, self.winfo_toplevel())
