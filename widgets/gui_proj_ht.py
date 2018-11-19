__all__ = [
    "GUIProjectHistoryTracker"
]

from qemu import (
    PCIExpressDeviceDescription,
    PCIId,
    DOp_SetAttr,
    DOp_SetPCIIdAttr,
    ProjectHistoryTracker
)
from common import (
    mlget as _
)
from .gui_editing import (
    GUIPOp_SetBuildPath
)

class GUIProjectHistoryTracker(ProjectHistoryTracker):
    def __init__(self, *args, **kw):
        super(GUIProjectHistoryTracker, self).__init__(*args, **kw)

        self.operation_strings = {}

        for op in self.get_branch():
            self.on_operation(op)

        self.watch_changed(self.on_operation)

        # use initial operation description as description of its sequence
        self.sequence_strings = {
            self.history.root.seq : self.operation_strings[self.history.root]
        }

    def on_operation(self, op):
        if op not in self.operation_strings:
            self.operation_strings[op] = op.__description__()

    def set_sequence_description(self, desc):
        self.sequence_strings[self.current_sequence] = desc

    def start_new_sequence(self, prev_seq_desc = None):
        if prev_seq_desc is not None:
            self.set_sequence_description(prev_seq_desc)

        super(GUIProjectHistoryTracker, self).start_new_sequence()

    def commit(self, *args, **kw):
        seq_desc = kw.pop("sequence_description", None)

        if seq_desc is not None:
            self.sequence_strings[self.current_sequence] = seq_desc

        super(GUIProjectHistoryTracker, self).commit(*args, **kw)

    def all_pci_ids_2_objects(self):
        for pci_desc in self.p.descriptions:
            if not isinstance(pci_desc, PCIExpressDeviceDescription):
                continue
            self.pci_ids_2_objects(pci_desc)

        self.commit(
            sequence_description = _("Fixing up PCI identifiers.")
        )

    def pci_ids_2_objects(self, desc):
        desc_sn = desc.__sn__
        for attr in [ "vendor", "subsys_vendor" ]:
            val = getattr(desc, attr)
            if (val is not None) and (not isinstance(val, PCIId)):
                try:
                    val = next(PCIId.db.find_vendors(id = val))
                except StopIteration:
                    # no vendor id with such value is registered
                    continue

                self.stage(DOp_SetAttr, attr, None, desc_sn)
                self.stage(DOp_SetPCIIdAttr, attr, val, desc_sn)

        self.commit(new_sequence = False)

        for attr, vendor_attr in [
            ("device", "vendor"),
            ("subsys", "subsys_vendor")
        ]:
            val = getattr(desc, attr)
            vendor = getattr(desc, vendor_attr)

            if  (val is not None) and (not isinstance(val, PCIId)):
                if vendor is None:
                    try:
                        val = next(PCIId.db.find_devices(id = val))
                    except StopIteration:
                        # No device id with such value is registered
                        continue
                else:
                    try:
                        val = next(PCIId.db.find_devices(
                            id = val,
                            vendor = vendor
                        ))
                    except StopIteration:
                        # no device id with such value is registered for the
                        # vendor
                        try:
                            val = next(PCIId.db.find_devices(id = val))
                        except StopIteration:
                            # No device id with such value is registered
                            continue

                self.stage(DOp_SetAttr, attr, None, desc_sn)
                self.stage(DOp_SetPCIIdAttr, attr, val, desc_sn)

        val = getattr(desc, "pci_class")
        if (val is not None) and (not isinstance(val, PCIId)):
            try:
                val = PCIId.db.get_class(name = val)
            except:
                try:
                    val = next(PCIId.db.find_classes(id = val))
                except StopIteration:
                    # no class id with such value is registered
                    return

            self.stage(DOp_SetAttr, "pci_class", None, desc_sn)
            self.stage(DOp_SetPCIIdAttr, "pci_class", val, desc_sn)

    def all_pci_ids_2_values(self):
        for pci_desc in self.p.descriptions:
            if not isinstance(pci_desc, PCIExpressDeviceDescription):
                continue
            self.pci_ids_2_values(pci_desc)

        self.commit(
            sequence_description =
                _("Converting PCI identifiers to numeric values.")
        )

    def pci_ids_2_values(self, desc):
        desc_sn = desc.__sn__
        for attr in [
            "vendor",
            "subsys_vendor",
            "device",
            "subsys",
            "pci_class"
        ]:
            val = getattr(desc, attr)
            if (val is not None) and isinstance(val, PCIId):
                val = val.id

                self.stage(DOp_SetPCIIdAttr, attr, None, desc_sn)
                self.stage(DOp_SetAttr, attr, val, desc_sn)

    def set_build_path(self, path):
        if self.p.build_path == path:
            return

        self.stage(GUIPOp_SetBuildPath, path)
        self.commit(sequence_description =
            _("Qemu build path configuration.")
        )
