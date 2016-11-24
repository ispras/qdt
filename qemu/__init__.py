from source import \
    Header, \
    Type, \
    Function, \
    Macro, \
    Structure, \
    add_base_types

from version_description import \
    QemuVersionDescription, \
    qvd_create, \
    qvd_get, \
    qvd_get_registered, \
    qvds_load, \
    qvds_load_with_cache, \
    qvds_init_cache, \
    forget_build_path, \
    load_build_path_list, \
    account_build_path

from pci_ids import \
    pci_id_db, \
    PCIClassification

from sysbusdevice import \
    SysBusDeviceStateStruct, \
    SysBusDeviceType

from pcie import \
    PCIEDeviceStateStruct, \
    PCIEDeviceType
    
from qom import \
    QemuTypeName, \
    QOMType

from machine import \
    MachineType

from machine_description import \
    Node, \
    MachineNode, \
    BusNode, \
    I2CBusNode, \
    SystemBusNode, \
    SystemBusDeviceNode, \
    PCIExpressBusNode, \
    PCIExpressDeviceNode, \
    ISABusNode, \
    IDEBusNode, \
    DeviceNode, \
    IRQLine, \
    IRQHub, \
    QOMPropertyType, \
    QOMPropertyTypeLink, \
    QOMPropertyTypeString, \
    QOMPropertyTypeBoolean, \
    QOMPropertyTypeInteger, \
    QOMPropertyValue, \
    MemoryNodeHasNoSuchParent, \
    MemoryNode, \
    MemoryAliasNode, \
    MemoryRAMNode, \
    MemoryROMNode

from project import \
    QOMDescription, \
    QProject

from device_description import \
    SysBusDeviceDescription, \
    PCIExpressDeviceDescription

from version import \
    initialize as qemu_version_initialize, \
    get_vp, \
    get_vs

from machine_editing import \
    MachineOperation, \
        MachineNodeOperation, \
            MOp_AddMemChild, \
                MOp_RemoveMemChild, \
            MachineNodeAdding, \
                MachineNodeDeletion, \
                    MOp_DelMemoryNode, \
                MOp_AddMemoryNode, \
                MOp_AddBus, \
                    MOp_DelBus, \
                MOp_AddDevice, \
                    MOp_DelDevice, \
            MOp_DelIRQLine, \
                MOp_AddIRQLine, \
            MOp_AddIRQHub, \
                MOp_DelIRQHub, \
            MachineDeviceSetAttributeOperation, \
                MachineNodeSetLinkAttributeOperation, \
                MOp_PCIDevSetSlot, \
                MOp_PCIDevSetFunction, \
                MOp_PCIDevSetMultifunction, \
            MachineIOMappingOperation, \
                MOp_DelIOMapping, \
                MOp_AddIOMapping, \
                MOp_SetIOMapping, \
            MOp_SetDevParentBus, \
            MOp_SetDevQOMType, \
            MachineDevicePropertyOperation, \
                MOp_DelDevProp, \
                MOp_AddDevProp, \
                MOp_SetDevProp, \
        MOp_SetChildBus

from project_editing import \
    QemuObjectCreationHelper, \
    ProjectOperation, \
        POp_AddDesc, \
            POp_DelDesc, \
        DescriptionOperation

from project_history_tracker import \
    ProjectHistoryTracker

from qom_editing import \
    DOp_SetAttr

from predefined_types import \
    add_types

import os

def initialize(qemu_src):
    VERSION_path = os.path.join(qemu_src, 'VERSION')

    if not os.path.isfile(VERSION_path):
        raise Exception("{} does not exists\n".format(VERSION_path))

    VERSION_f = open(VERSION_path)
    qemu_version = VERSION_f.readline().rstrip("\n")
    VERSION_f.close()

    print("Qemu version is {}".format(qemu_version))

    include_path = os.path.join(qemu_src, 'include')

    header_db_fname = "header_db.json"
    if os.path.isfile(header_db_fname):
        print("Loading Qemu header inclusion tree from " + header_db_fname)
        Header.load_header_db(header_db_fname)
    else:
        print("Building Qemu header inclusion tree")
        Header.build_inclusions(include_path)

    print("Saving Qemu header inclusion tree to " + header_db_fname)
    Header.save_header_db(header_db_fname)

    qemu_version_initialize(qemu_version)

    # Search for PCI Ids
    PCIClassification.build()

    get_vp()["qemu types definer"]()

