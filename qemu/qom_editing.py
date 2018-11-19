__all__ = [
    "SetDescriptionReferenceAttribute"
      , "DOp_SetPCIIdAttr"
  , "DOp_SetAttr"
]

from .project_editing import (
    DescriptionOperation
)
from copy import (
    deepcopy as dcp
)
from common import (
    mlget as _
)
from .pci_ids import (
    PCIVendorId,
    PCIDeviceId,
    PCIClassId
)

class DOp_SetAttr(DescriptionOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        DescriptionOperation.__init__(self, *args, **kw)

        self.attr = str(attribute_name)
        self.val = dcp(new_value)

    def __read_set__(self):
        return DescriptionOperation.__read_set__(self) + [
            self.sn
        ]

    def __write_set__(self):
        return DescriptionOperation.__write_set__(self) + [
            (self.sn, str(self.attr))
        ]

    def __backup__(self):
        self.old_val = dcp(getattr(self.find_desc(), self.attr))

    def __do__(self):
        setattr(self.find_desc(), self.attr, dcp(self.val))

    def __undo__(self):
        setattr(self.find_desc(), self.attr, dcp(self.old_val))

    def __description__(self):
        attr = self.attr
        if attr == "name":
            name = self.old_val
        else:
            name = self.find_desc().name
        return _("Set '%s' of '%s' to '%s'.") % (
            attr,
            name,
            str(self.val)
        )

class SetDescriptionReferenceAttribute(DescriptionOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        DescriptionOperation.__init__(self, *args, **kw)

        self.attr = str(attribute_name)
        self.val = new_value

    def __read_set__(self):
        # Note that new referenced value is probably to be in read set.
        return DescriptionOperation.__read_set__(self) + [
            self.sn
        ]

    def __write_set__(self):
        return DescriptionOperation.__write_set__(self) + [
            (self.sn, str(self.attr))
        ]

    def __backup__(self):
        self.old_val = getattr(self.find_desc(), self.attr)

    def __do__(self):
        setattr(self.find_desc(), self.attr, self.val)

    def __undo__(self):
        setattr(self.find_desc(), self.attr, self.old_val)

def get_pci_id_kind_str(pci_id):
    if type(pci_id) is PCIVendorId:
        return _("vendor")
    elif type(pci_id) is PCIDeviceId:
        return _("device")
    elif type(pci_id) is PCIClassId:
        return _("class")

def gen_pci_id_str(pci_id):
    return _("%s %s (%s)") % (
        get_pci_id_kind_str(pci_id),
        pci_id.name,
        pci_id.id
    )

class DOp_SetPCIIdAttr(SetDescriptionReferenceAttribute):

    def __description__(self):
        name = self.find_desc().name
        if self.old_val is None:
            return _("Set '%s' of '%s' to %s") % (
                self.attr, name, gen_pci_id_str(self.val)
            )
        elif self.val is None:
            return _("Reset '%s' of '%s'.") % (self.attr, name)
        else:
            return _("Change '%s' of '%s' from %s to %s") % (
                self.attr, name,
                gen_pci_id_str(self.old_val),
                gen_pci_id_str(self.val)
            )
