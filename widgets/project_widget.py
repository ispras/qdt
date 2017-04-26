from .var_widgets import \
    VarMenu, \
    VarTreeview

from .close_button_notebook import \
    CloseButtonNotebook

from .machine_widget import \
    MachineDescriptionSettingsWidget

from qemu import \
    SysBusDeviceDescription, \
    PCIExpressDeviceDescription, \
    MachineNode

from six.moves.tkinter import \
    NO, \
    PanedWindow

from common import \
    CoTask, \
    mlget as _

from qemu import \
    MultipleQVCInitialization, \
    BadBuildPath, \
    qvd_get, \
    qvd_load_with_cache, \
    DOp_SetAttr, \
    POp_AddDesc

from .qom_settings import \
    QOMDescriptionSettingsWidget

from six.moves.tkinter_font import \
    Font

from .gui_frame import \
    GUIFrame

from six.moves.tkinter_ttk import \
    Scrollbar

from .add_desc_dialog import \
    AddDescriptionDialog

from .gui_editing import \
    GUIPOp_SetBuildPath, \
    POp_SetDescLayout

from .popup_helper import \
    TkPopupHelper

from six.moves.tkinter_messagebox import \
    showerror

from .qdc_gui_signal_helper import \
    QDCGUISignalHelper

class ReloadBuildPathTask(CoTask):
    def __init__(self, project_widget):
        self.pw = project_widget
        self.qvd = qvd_get(project_widget.p.build_path)
        CoTask.__init__(self, generator = self.begin())

    def begin(self):
        if self.qvd is None:
            yield self.qvd.co_init_cach

    def on_finished(self):
        self.qvd.use()
        self.pw.qsig_emit("qvd_switched")

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

class ProjectWidget(PanedWindow, TkPopupHelper, QDCGUISignalHelper):
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
            self.pht.watch_changed(self.on_project_changed)

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

        for desc_name, lys in self.p.layouts.items():
            for l in lys.values():
                if not l.shown:
                    continue

                if l.widget is None:
                    desc = next(self.p.find(name = desc_name))

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

        self.tv_descs.bind("<Delete>", self.on_key_delete, "+")

        self.nb_descriptions.bind("<<NotebookTabClosed>>",
            self.on_notebook_tab_closed)

        self.__account_build_path = self.after(1, self.account_build_path)

        self.bind("<Destroy>", self.__on_destroy__, "+")

        self.qsig_watch("qvd_switched", self.on_qvd_switched)
        self.qsig_watch("generation_finished", self.on_generation_finished)

    def __on_destroy__(self, event):
        if self.pht is not None:
            self.pht.unwatch_changed(self.on_project_changed)

        try:
            self.after_cancel(self.__account_build_path)
        except AttributeError:
            pass

        try:
            self.tm.remove(self.reload_build_path_task)
        except AttributeError:
            pass

        self.qsig_unwatch("qvd_switched", self.on_qvd_switched)
        self.qsig_unwatch("generation_finished", self.on_generation_finished)

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

    def delete_description(self, desc):
        self.pht.stage(POp_SetDescLayout, None, desc)
        self.pht.delete_description(desc)

    def on_delete_description(self):
        item = self.tv_descs.selection()[0]
        name = self.tv_descs.item(item)["text"]
        desc = next(self.p.find(name = name))

        # Layout refreshing is required because the layout of widget
        # representing description being deleted, must be saved too.
        # TODO: Only corresponding layout should be refreshed.
        self.refresh_layouts()

        self.delete_description(desc)

        self.pht.commit()

        self.notify_popup_command()

    def on_key_delete(self, event):
        # Description deletion may cause item identifiers to become invalid.
        # Hence, first look up all descriptions to be deleted.
        descs_to_del = []
        for item in self.tv_descs.selection():
            name = self.tv_descs.item(item)["text"]
            descs_to_del.append(next(self.p.find(name = name)))

        if descs_to_del:
            # Layout refreshing is required because the layout of widget
            # representing description being deleted, must be saved too.
            # TODO: Only corresponding layout should be refreshed.
            self.refresh_layouts()

            for desc in descs_to_del:
                self.delete_description(desc)

            self.pht.commit(
                sequence_description = _("Selected descriptions deletion")
            )

    def account_build_path(self):
        del self.__account_build_path

        self.pht.all_pci_ids_2_values()

        if self.p.build_path is None:
            return

        self.reload_build_path()

    def reload_build_path(self):
        if self.tm:
            # If task manager is available then use background task
            try:
                self.tm.remove(self.reload_build_path_task)
            except AttributeError:
                pass
            else:
                del self.reload_build_path_task

            try:
                self.reload_build_path_task = ReloadBuildPathTask(self)
            except BadBuildPath as bbpe:
                showerror(_("Bad build path").get(), str(bbpe))
            else:
                self.tm.enqueue(self.reload_build_path_task)
        else:
            """ If no task manager is available then account build path right
            now. It will cause GUI to freeze but there are no more options. """

            try:
                qvd = qvd_load_with_cache(self.p.build_path)
            except BadBuildPath as bbpe:
                showerror(_("Bad build path").get(), str(bbpe))
            else:
                qvd.use()
                self.pht.all_pci_ids_2_objects()

    def on_project_changed(self, op):
        if isinstance(op, POp_AddDesc):
            self.tv_descs.update()

            for desc_name, lys in self.p.layouts.items():
                try:
                    next(self.p.find(name = desc_name))
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
        elif isinstance(op, GUIPOp_SetBuildPath):
            try:
                self.__account_build_path
            except AttributeError:
                self.__account_build_path = self.after(1,
                    self.account_build_path
                )

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
        layouts = sorted(
            self.p.get_layout_objects(name),
            key = lambda l : l.lid
        )
        widgets = [ l.widget for l in layouts if l.widget is not None ]

        if not widgets:
            desc = next(self.p.find(name = name))
            w = self.gen_widget(desc)

            for l in layouts:
                try:
                    w.set_layout(l.opaque)
                except:
                    continue
                break
            else:
                l = self.p.add_layout(name, w.gen_layout())
            # The layout now is represented on the widget
            l.widget = w

            l.shown = True

            self.nb_descriptions.add(w, text = name)
            for tab_id in self.nb_descriptions.tabs():
                if self.nb_descriptions.tab(tab_id)["text"] == name:
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
        else:
            w = QOMDescriptionSettingsWidget(desc, self)
        return w

    def add_description(self):
        AddDescriptionDialog(self.pht, self.winfo_toplevel())

    def on_qvd_switched(self):
        pht = self.pht
        if pht is not None:
            pht.all_pci_ids_2_objects()

    def on_generation_finished(self):
        pht = self.pht
        if pht is not None:
            pht.all_pci_ids_2_values()

        try:
            qvd = qvd_get(self.p.build_path)
        except BadBuildPath:
            pass
        else:
            if qvd.qvc is not None:
                qvd.forget_cache()

        self.reload_build_path()
