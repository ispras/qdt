from .gui_frame import \
    GUIFrame

from .var_widgets import \
    VarCombobox

from six.moves.tkinter_ttk import \
    Combobox

from common import \
    mlget as _

from qemu import \
    PCIId, \
    PCIClassId, \
    PCIVendorId, \
    PCIDeviceId

kind2idx = {
    PCIClassId  : 0,
    PCIVendorId : 1,
    PCIDeviceId : 2,
    type(None) : 3
}

idx2kind = {}
for kind, idx in kind2idx.iteritems():
    idx2kind[idx] = kind

def get_db(idx):
    if idx == 0:
        return PCIId.db.classes.iteritems()
    elif idx == 1:
        return PCIId.db.vendors.iteritems()
    elif idx == 2:
        return PCIId.db.devices.iteritems()
    return None

def get_db_sorted(idx):
    dbiter = get_db(idx)

    if dbiter is None:
        return None

    return sorted(dbiter, key = lambda (n, desc) : n)

class PCIIdWidget(GUIFrame):
    def __init__(self, idvariable, *args, **kw):
        GUIFrame.__init__(self, *args, **kw)

        self.var = idvariable
        self.var.trace_variable("w", self.__on_var_changed__)

        self.grid()

        self.rowconfigure(0, weight = 0)
        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)
        self.columnconfigure(2, weight = 0)

        self.kind_cb = cb = VarCombobox(self,
            values = [
                _("PCI class code"),
                _("Vendor ID"),
                _("Device ID"),
                _("Not specified")
            ],
            state = "readonly"
        )
        cb.grid(row = 0, column = 0, sticky = "NEWS")
        cb.bind("<<ComboboxSelected>>", self.__on_kind_changed__, "+")

        self.cb_name = cb = Combobox(self, state = "readonly")
        cb.grid(row = 0, column = 1, sticky = "NEWS")
        cb.bind("<<ComboboxSelected>>", self.__on_name_changed__, "+")

        self.cb_id = cb = Combobox(self, state = "readonly")
        cb.grid(row = 0, column = 2, sticky = "NEWS")
        cb.bind("<<ComboboxSelected>>", self.__on_id_changed__, "+")

        self.after_idle(self.__refresh__)

    def find_idx(self, **kw):
        for idx, (name, desc) in enumerate(self.kind_db):
            for key, value in kw.iteritems():
                if getattr(desc, key) == value:
                    return idx
        raise Exception("Incorrect find request: " + str(kw))

    def __on_kind_changed__(self, *args):
        cur_idx = self.kind_cb.current()
        cur = idx2kind[cur_idx]

        if type(self.var.get()) is cur:
            return

        self.__on_changed__()

    def __on_name_changed__(self, *args):
        if self.kind_db is None:
            return

        cur_idx = self.cb_name.current()
        cur = self.kind_db[cur_idx][0]

        if cur == self.var.get().name:
            return

        self.__on_changed__()

    def __on_id_changed__(self, *args):
        if self.kind_db is None:
            return

        cur_idx = self.cb_id.current()
        cur = self.kind_db[cur_idx][1].id

        if cur == self.var.get().id:
            return

        self.__on_changed__()

    def __sync_name_and_id_lists__(self):
        if self.kind_db is None:
            self.cb_name.config(values = [])
            self.cb_id.config(values = [])
        else:
            names, ids = [], []
            for name, desc in self.kind_db:
                names.append(name)
                ids.append(desc.id)

            self.cb_name.config(values = names)
            self.cb_id.config(values = ids)

    def __on_changed__(self):
        pci_id = self.var.get()
        var_kind_idx = kind2idx[type(pci_id)]
        cb_kind_idx = self.kind_cb.current()

        if cb_kind_idx != var_kind_idx:
            # Select first of existing class/vendor/device
            self.kind_db = get_db_sorted(cb_kind_idx)
            self.__sync_name_and_id_lists__()

            if self.kind_db is None:
                self.var.set(None)
            else:
                self.var.set(self.kind_db[0][1])
            return

        if pci_id is None:
            return

        name_idx = self.cb_name.current()
        name = self.kind_db[name_idx][0]

        if pci_id.name != name:
            self.var.set(self.kind_db[name_idx][1])
        else:
            id_idx = self.cb_id.current()
            id_val = self.kind_db[id_idx][1].id

            if pci_id.id != id_val:
                self.var.set(self.kind_db[id_idx][1])

    def __on_var_changed__(self, *args):
        self.__refresh__()

    def __refresh__(self):
        pci_id = self.var.get()

        kind_idx = kind2idx[type(pci_id)]
        cur_kind_idx = self.kind_cb.current()

        if cur_kind_idx != kind_idx:
            self.kind_db = get_db_sorted(kind_idx)
            self.__sync_name_and_id_lists__()
            self.kind_cb.current(kind_idx)

        if pci_id is None:
            if self.cb_name.get() != "":
                self.cb_name.set("")
        else:
            cur_name_idx = self.cb_name.current()
            var_name_idx = self.find_idx(name = pci_id.name)
            if cur_name_idx != var_name_idx:
                self.cb_name.current(var_name_idx)

        if pci_id is None:
            if self.cb_id.get() != "":
                self.cb_id.set("")
        else:
            cur_id_idx = self.cb_id.current()
            var_id_idx = self.find_idx(id = pci_id.id)
            if cur_id_idx != var_id_idx:
                self.cb_id.current(var_id_idx)
