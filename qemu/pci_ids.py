import re

from source import Type

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
        
        v = self.get_vendor(vendor_name, vid)
        
        if not name == None: 
            dev_key = PCIClassification.gen_device_key(v.name, name)
            try:
                d = self.devices[dev_key]
                if not d.id == did:
                    raise Exception("Device %s, vendor %s, device id %s/%s" %
                        d.name, v.name, d.id, did) 
            except KeyError:
                if did == None:
                    raise Exception("Cannot create device %s because of no id \
 was specified" % did)

                d = PCIDeviceId(v.name, name, did)
        else:
            raise Exception("Not implemented case")

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