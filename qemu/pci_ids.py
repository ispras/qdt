__all__ = [
    "PCIVendorIdNetherExistsNorCreated"
  , "PCIVendorIdAlreadyExists"
  , "PCIDeviceIdAlreadyExists"
  , "PCIVendorIdMismatch"
  , "PCIId"
      , "PCIVendorId"
      , "PCIDeviceId"
      , "PCIClassId"
  , "PCIClassification"
]

from re import (
    compile
)
from source import (
    Type,
    Macro
)
from common import (
    co_find_eq
)
from six.moves import (
    range as xrange
)

re_pci_vendor = compile("PCI_VENDOR_ID_([A-Z0-9_]+)")
re_pci_device = compile("PCI_DEVICE_ID_([A-Z0-9_]+)")
re_pci_class = compile("PCI_CLASS_([A-Z0-9_]+)")


class PCIVendorIdAlreadyExists(RuntimeError):
    pass


class PCIDeviceIdAlreadyExists(RuntimeError):
    pass


class PCIVendorIdNetherExistsNorCreated(RuntimeError):
    pass


class PCIVendorIdMismatch(ValueError):
    pass


# TODO: create named exception instead of any Exception


class PCIId(object):
    db = None # at the end of module the value will be defined

    def __init__(self, name, id):
        self.name = name
        self.id = id

    def find_macro(self):
        raise Exception("The virtual method is not implemented.")

    def __str__(self):
        return '"%s"' % self.id

    __repr__ = __str__


class PCIVendorId(PCIId):

    def __init__(self, vendor_name, vendor_id):
        if vendor_name in PCIId.db.vendors.keys():
            raise PCIVendorIdAlreadyExists(vendor_name)

        PCIId.__init__(self, vendor_name, vendor_id)

        self.device_pattern = compile(
                "PCI_DEVICE_ID_%s_([A-Z0-9_]+)" % self.name)

        PCIId.db.vendors[self.name] = self

    def find_macro(self):
        return Type["PCI_VENDOR_ID_%s" % self.name]

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("vendor_name = " + gen.gen_const(self.name))
        gen.gen_field("vendor_id = " + gen.gen_const(self.id))
        gen.gen_end()


class PCIDeviceId(PCIId):

    def __init__(self, vendor_name, device_name, device_id):
        dev_key = PCIClassification.gen_device_key(vendor_name, device_name)
        if dev_key in PCIId.db.devices.keys():
            raise PCIDeviceIdAlreadyExists("Vendor %s, Device %s" % vendor_name,
                    device_name)

        PCIId.__init__(self, device_name, device_id)

        if not vendor_name in PCIId.db.vendors.keys():
            self.vendor = PCIVendorId(vendor_name, 0xFFFF)
        else:
            self.vendor = PCIId.db.vendors[vendor_name]

        PCIId.db.devices[dev_key] = self

    def find_macro(self):
        return Type["PCI_DEVICE_ID_%s_%s" % (self.vendor.name, self.name)]

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("vendor_name = " + gen.gen_const(self.vendor.name))
        gen.gen_field("device_name = " + gen.gen_const(self.name))
        gen.gen_field("device_id = " + gen.gen_const(self.id))
        gen.gen_end()


class PCIClassId(PCIId):

    def __init__(self, class_name, class_id):
        if class_name in PCIId.db.classes.keys():
            raise Exception("PCI class %s already exists" % class_name)

        PCIId.__init__(self, class_name, class_id)

        PCIId.db.classes[self.name] = self

    def find_macro(self):
        return Type["PCI_CLASS_%s" % self.name]

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_field("class_name = " + gen.gen_const(self.name))
        gen.gen_field("class_id = " + gen.gen_const(self.id))
        gen.gen_end()


class PCIClassification(object):

    def __init__(self, built = False):
        self.vendors = {}
        self.devices = {}
        self.classes = {}
        self.built = built

    def clear(self):
        self.vendors = {}
        self.devices = {}
        self.classes = {}
        self.built = False

    def find_vendors(self, **kw):
        return co_find_eq(self.vendors.values(), **kw)

    def find_devices(self, **kw):
        return co_find_eq(self.devices.values(), **kw)

    def find_classes(self, **kw):
        return co_find_eq(self.classes.values(), **kw)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        if self.built:
            gen.gen_field("built = " + gen.gen_const(True))
        gen.gen_end()

        gen.line(gen.nameof(self) + ".tmp = PCIId.db")
        gen.line("PCIId.db = " + gen.nameof(self))

        for pci_id in self.vendors.values():
            pci_id.__gen_code__(gen)

        for pci_id in self.devices.values():
            pci_id.__gen_code__(gen)

        for pci_id in self.classes.values():
            pci_id.__gen_code__(gen)

        gen.line("PCIId.db = " + gen.nameof(self) + ".tmp")
        gen.line("del " + gen.nameof(self) + ".tmp")

    def gen_uniq_vid(self):
        for i in xrange(0, 0xFFFF):
            uid = "0x%X" % i
            for v in self.vendors.values():
                if v.id.upper() == uid:
                    break
            else:
                return uid
        # no uniq ID
        return "0xDEAD"

    def gen_uniq_did(self):
        for i in xrange(0, 0xFFFF):
            uid = "0x%X" % i
            for d in self.devices.values():
                if d.id.upper() == uid:
                    break
            else:
                return uid
        # no uniq ID
        return "0xBEAF"

    @staticmethod
    def build():
        db = PCIId.db

        if db.built:
            db.clear()

        for t in Type.reg.values():
            if type(t) == Macro:
                mi = re_pci_vendor.match(t.name)
                if mi:
                    PCIVendorId(mi.group(1), t.text)
                    continue

                mi = re_pci_class.match(t.name)
                if mi:
                    # print 'PCI class %s' % mi.group(1)
                    PCIClassId(mi.group(1), t.text)
                    continue

        # All PCI vendors must be defined before any device.
        for t in Type.reg.values():
            if type(t) == Macro:
                mi = re_pci_device.match(t.name)
                if mi:
                    for v in db.vendors.values():
                        mi = v.device_pattern.match(t.name)
                        if mi:
                            PCIDeviceId(v.name, mi.group(1), t.text)
                            break
                    continue

        db.built = True

    @staticmethod
    def gen_device_key(vendor_name, device_name):
        return vendor_name + "_" + device_name

    def get_class(self, name = None, cid = None):
        if name is None:
            if not isinstance(cid, str):
                raise ValueError("Class ID value must be a string")

            tmp = self.find_classes(id = cid)
            try:
                c = next(tmp)
            except StopIteration:
                raise Exception("There is no known class ID for value %s and"
                    " no one can be created because of the name is not"
                    " given" % cid
                )
        else:
            try:
                c = self.classes[name]
                if cid is not None and c.id != cid:
                    raise Exception("PCI class ID  %s already exists but is "
                        "assigned different value %s / %s." % (name, c.id, cid)
                    )
            except KeyError:
                if cid is None:
                    raise Exception("There is no known class ID with name %s"
                        " and no one can be created because of the value is"
                        " not given" % name
                    )
                else:
                    c = PCIClassId(name, cid)

        return c

    def get_device(self, name = None, vendor_name = None, did = None, 
            vid = None):
        if did is not None and type(did) is not str:
            raise Exception("Device id must be a string")

        if vid is not None:
            try:
                v = self.get_vendor(vendor_name, vid)
            except PCIVendorIdNetherExistsNorCreated as e:
                if vendor_name is not None:
                    raise e
                v = None
        elif vendor_name is not None:
            try:
                v = self.get_vendor(vendor_name, vid)
            except PCIVendorIdNetherExistsNorCreated:
                v = self.get_vendor(vendor_name, self.gen_uniq_vid())
        else:
            if name is None:
                if did is None:
                    raise Exception("No identification information was got!")
                # Return first device with such ID
                for d in self.devices.values():
                    if did.upper() == d.id.upper():
                        return d
                raise Exception("No device with id %s was found!" % did.upper())
            # Try get vendor by device name
            for v in self.vendors.values():
                if v.device_pattern.match(name):
                    break
            else:
                raise Exception("Cannot get vendor by device name %s." % name)

        if name is not None:
            dev_key = PCIClassification.gen_device_key(v.name, name)
            try:
                d = self.devices[dev_key]
                if not d.id == did:
                    raise Exception("Device %s, vendor %s, device id %s/%s" %
                        d.name, v.name, d.id, did) 
            except KeyError:
                if did is None:
                    did = self.gen_uniq_did()

                d = PCIDeviceId(v.name, name, did)
        else:
            if did is None:
                did = self.gen_uniq_did()
            name = "UNKNOWN_DEVICE_%X" % did

            d = PCIDeviceId(v.name, name, did)

        return d

    def get_vendor(self, name = None, vid = None):
        if vid is not None and type(vid) is not str:
            raise Exception("Vendor id must be a string")

        if name is not None:
            try:
                v = self.vendors[name]
                if vid is not None and v.id != vid:
                    raise PCIVendorIdMismatch("Vendor %s, Id: %s/%s" %
                            name, v.id, vid)
            except:
                if vid is not None:
                    v = PCIVendorId(name, vid)
                else:
                    raise PCIVendorIdNetherExistsNorCreated("Vendor %s does not\
 exists and cannot be created because of no id is specified" % name)
            return v
        elif vid is not None:
            v = None
            for ven in self.vendors.values():
                if ven.id == vid:
                    v = ven
                    break
            if v is None:
                raise PCIVendorIdNetherExistsNorCreated("No vendor with id %s\
 was found and no one can be created because of no name is\
 specified" % id)

            return v

        raise Exception("At least one vendor name or id must be specified")


PCIId.db = PCIClassification()
