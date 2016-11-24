import re

from source import \
    Type, \
    Macro

re_pci_vendor = re.compile("PCI_VENDOR_ID_([A-Z0-9_]+)")
re_pci_device = re.compile("PCI_DEVICE_ID_([A-Z0-9_]+)")
re_pci_class = re.compile("PCI_CLASS_([A-Z0-9_]+)")

class PCIVendorIdAlreadyExists (Exception):
    pass

class PCIDeviceIdAlreadyExists (Exception):
    pass

class PCIVendorIdNetherExistsNorCreate(Exception):
    pass

class PCIVendorIdMismatch(Exception):
    pass

"""
TODO: create named exception instead of any Exception
"""

class PCIId:

    def find_macro(self):
        raise Exception("The virtual method is not implemented.")

class PCIVendorId (PCIId):
    def __init__(self, vendor_name, vendor_id):
        if vendor_name in pci_id_db.vendors.keys():
            raise PCIVendorIdAlreadyExists(vendor_name)

        self.name = vendor_name
        self.id = vendor_id

        self.device_pattern = re.compile(
                "PCI_DEVICE_ID_%s_([A-Z0-9_]+)" % self.name)

        pci_id_db.vendors[self.name] = self

    def find_macro(self):
        return Type.lookup("PCI_VENDOR_ID_%s" % self.name)

class PCIDeviceId (PCIId):
    def __init__(self, vendor_name, device_name, device_id):
        dev_key = PCIClassification.gen_device_key(vendor_name, device_name)
        if dev_key in pci_id_db.devices.keys():
            raise PCIDeviceIdAlreadyExists("Vendor %s, Device %s" % vendor_name,
                    device_name)

        if not vendor_name in pci_id_db.vendors.keys():
            self.vendor = PCIVendorId(vendor_name, 0xFFFF)
        else:
            self.vendor = pci_id_db.vendors[vendor_name]

        self.name = device_name
        self.id = device_id

        pci_id_db.devices[dev_key] = self

    def find_macro(self):
        return Type.lookup("PCI_DEVICE_ID_%s_%s" % 
                (self.vendor.name, self.name))

class PCIClassId (PCIId):
    def __init__(self, class_name, class_id):
        if class_name in pci_id_db.classes.keys():
            raise Exception("PCI class %s already exists" % class_name)

        self.name = class_name
        self.id = class_id

        pci_id_db.classes[self.name] = self

    def find_macro(self):
        return Type.lookup("PCI_CLASS_%s" % self.name)

class PCIClassification:
    def __init__(self):
        self.vendors = {}
        self.devices = {}
        self.classes = {}

    def gen_uniq_vid(self):
        for i in xrange(0, 0xFFFF):
            for v in self.vendors.values():
                if v.id.upper() == "0x%X" % i:
                    break;
            else:
                return "0x%X" % i
        # no uniq ID
        return "0xDEAD"

    def gen_uniq_did(self):
        for i in xrange(0, 0xFFFF):
            for d in self.devices.values():
                if d.id.upper() == "0x%X" % i:
                    break;
            else:
                return "0x%X" % i
        # no uniq ID
        return "0xBEAF"

    @staticmethod
    def build():
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
                    for v in pci_id_db.vendors.values():
                        mi = v.device_pattern.match(t.name)
                        if mi:
                            PCIDeviceId(v.name, mi.group(1), t.text)
                            break;
                    continue

    @staticmethod
    def gen_device_key(vendor_name, device_name):
        return vendor_name + "_" + device_name

    def get_class(self, name):
        try:
            c = self.classes[name]
        except KeyError:
            raise Exception("Unknown PCI class %s" % name)

        return c

    def get_device(self, name = None, vendor_name = None, did = None, 
            vid = None):
        if not did == None and not type(did) == str:
            raise Exception("Device id must be a string")

        if vid is not None:
            try:
                v = self.get_vendor(vendor_name, vid)
            except PCIVendorIdNetherExistsNorCreate as e:
                if vendor_name is not None:
                    raise e
                v = None
        elif vendor_name is not None:
            try:
                v = self.get_vendor(vendor_name, vid)
            except PCIVendorIdNetherExistsNorCreate:
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
        if not vid == None and not type(vid) == str:
            raise Exception("Vendor id must be a string")

        if not name == None:
            try:
                v = self.vendors[name]
                if not vid == None and not v.id == vid:
                    raise PCIVendorIdMismatch("Vendor %s, Id: %s/%s" %
                            name, v.id, vid)
            except:
                if not vid == None:
                    v = PCIVendorId(name, vid)
                else:
                    raise PCIVendorIdNetherExistsNorCreate("Vendor %s does not\
 exists and cannot be created because of no id is specified" % name)
            return v
        elif not vid == None:
            v = None
            for ven in self.vendors.values():
                if ven.id == vid:
                    v = ven
                    break
            if v == None:
                raise PCIVendorIdNetherExistsNorCreate("No vendor with id %s\
 was found and no one can be created because of no name is\
 specified" % id)

            return v
        raise Exception("At least one vendor name or id must be specified")

pci_id_db = PCIClassification()
