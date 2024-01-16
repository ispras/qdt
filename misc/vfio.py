#!/usr/bin/python

""" VFIO API usage example with pure standard Python API.
"""

# Some of this code is based on folowing...
# - https://www.kernel.org/doc/Documentation/vfio.txt
# - qemu: hw/vfio/*
# - qemu: include/hw/vfio/*

from bisect import (
    insort,
)
from collections import (
    defaultdict,
)
from ctypes import (
    addressof,
    Array,
    byref,
    cast,
    cdll,
    c_int,
    c_long,
    create_string_buffer,
    c_size_t,
    c_uint16,
    c_uint32,
    c_uint64,
    c_uint8,
    c_void_p,
    POINTER,
    sizeof,
    Structure,
)
from ctypes.util import (
    find_library,
)
from os import (
    listdir,
    readlink,
)
from os.path import (
    basename,
    exists,
    join,
)
from re import (
    compile,
)

# importing libc

libc_path = find_library("c")
print("libc_path = '%s'" % (libc_path,))

libc = cdll.LoadLibrary(libc_path)

vfio_pfx = join("/", "dev", "vfio")
vfio_path = join(vfio_pfx, "vfio")
b_vfio_path = vfio_path.encode("utf-8")

NULL = c_void_p(0)
c_off_t = c_long
c_p_int = POINTER(c_int)
c_p_uint32 = POINTER(c_uint32)

libc_open = libc.open
O_RDWR = 2

libc_close = libc.close
libc_ioctl = libc.ioctl

libc_pread = libc.pread

libc_mmap = libc.mmap
libc_mmap.argtypes = [c_void_p, c_size_t, c_int, c_int, c_int, c_off_t]
libc_mmap.restype = c_void_p
PROT_READ = 1
PROT_WRITE = 2
MAP_SHARED = 1

libc_munmap = libc.munmap

libc_errno = libc.errno

# PCI conf space
PCI_DID_VID_OFFSET   = 0
PCI_CLASS_REV_OFFSET = 8

# /usr/src/linux-headers-${KERNEL_VERSION}/include/uapi/asm-generic/ioctl.h
def _IO(type_, nr):
    return _IOC(_IOC_NONE, type_, nr, 0)

_IOC_NONE = 0

def _IOC(dir_, type_, nr, size):
    return (
        (dir_  << _IOC_DIRSHIFT)
      | (type_ << _IOC_TYPESHIFT)
      | (nr   << _IOC_NRSHIFT)
      | (size << _IOC_SIZESHIFT)
    )

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

# end of ioctl.h

# VFIO specifics
re_iommu_grp = compile("^[0-9]+$")

# /usr/src/linux-headers-${KERNEL_VERSION}/include/uapi/linux/vfio.h

VFIO_TYPE = ord(b';')
VFIO_BASE = 100

class vfio_info_cap_header(Structure):
    _fields_ = (
        ("id", c_uint16),       # Identifies capability
        ("version", c_uint16),  # Version specific to the capability ID
        ("next", c_uint32),     # Offset of next capability
    )

VFIO_API_VERSION = 0
VFIO_GET_API_VERSION = _IO(VFIO_TYPE, VFIO_BASE + 0)

VFIO_TYPE1_IOMMU = 1
VFIO_CHECK_EXTENSION = _IO(VFIO_TYPE, VFIO_BASE + 1)

VFIO_SET_IOMMU = _IO(VFIO_TYPE, VFIO_BASE + 2)

VFIO_GROUP_GET_STATUS = _IO(VFIO_TYPE, VFIO_BASE + 3)

VFIO_GROUP_FLAGS_VIABLE = 1 << 0
VFIO_GROUP_FLAGS_CONTAINER_SET = 1 << 1

class vfio_group_status(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
    )

VFIO_GROUP_SET_CONTAINER = _IO(VFIO_TYPE, VFIO_BASE + 4)
VFIO_GROUP_UNSET_CONTAINER = _IO(VFIO_TYPE, VFIO_BASE + 5)

VFIO_GROUP_GET_DEVICE_FD = _IO(VFIO_TYPE, VFIO_BASE + 6)

class vfio_device_info(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
        ("num_regions", c_uint32),  # Max region index + 1
        ("num_irqs", c_uint32),     # Max IRQ index + 1
    )

VFIO_DEVICE_FLAGS_RESET    = 1 << 0  # Device supports reset
VFIO_DEVICE_FLAGS_PCI      = 1 << 1  # vfio-pci device
VFIO_DEVICE_FLAGS_PLATFORM = 1 << 2  # vfio-platform device
VFIO_DEVICE_FLAGS_AMBA     = 1 << 3  # vfio-amba device
VFIO_DEVICE_FLAGS_CCW      = 1 << 4  # vfio-ccw device
VFIO_DEVICE_FLAGS_AP       = 1 << 5  # vfio-ap device

# region indices of PCI devices
# it's an `enum` in vfio.h
VFIO_PCI_BAR0_REGION_INDEX   = 0
VFIO_PCI_BAR1_REGION_INDEX   = 1
VFIO_PCI_BAR2_REGION_INDEX   = 2
VFIO_PCI_BAR3_REGION_INDEX   = 3
VFIO_PCI_BAR4_REGION_INDEX   = 4
VFIO_PCI_BAR5_REGION_INDEX   = 5
VFIO_PCI_ROM_REGION_INDEX    = 6
VFIO_PCI_CONFIG_REGION_INDEX = 7
VFIO_PCI_VGA_REGION_INDEX    = 8
VFIO_PCI_NUM_REGIONS         = 9

# it's an `enum` too
VFIO_PCI_INTX_IRQ_INDEX = 0
VFIO_PCI_MSI_IRQ_INDEX  = 1
VFIO_PCI_MSIX_IRQ_INDEX = 2
VFIO_PCI_ERR_IRQ_INDEX  = 3
VFIO_PCI_REQ_IRQ_INDEX  = 4
VFIO_PCI_NUM_IRQS       = 5

VFIO_DEVICE_GET_INFO = _IO(VFIO_TYPE, VFIO_BASE + 7)

VFIO_DEVICE_GET_REGION_INFO = _IO(VFIO_TYPE, VFIO_BASE + 8)

class vfio_region_sparse_mmap_area(Structure):
    _fields_ = (
        ("offset", c_uint64),  # Offset of mmap'able area within region
        ("size", c_uint64),    # Size of mmap'able area
    )

# This is an example, actual format must be defined at runtime.
class vfio_region_sparse_mmap_area_array(Array):
    _type_ = vfio_region_sparse_mmap_area
    _length_ = 1  # actual length is `nr_areas` below

VFIO_REGION_INFO_CAP_SPARSE_MMAP = 1
class vfio_region_info_cap_sparse_mmap(Structure):
    _fields_ = (
        ("header", vfio_info_cap_header),
        ("nr_areas", c_uint32),
        ("reserved", c_uint32),
        ("areas", vfio_region_sparse_mmap_area_array)
    )

VFIO_REGION_INFO_CAP_TYPE = 2
class vfio_region_info_cap_type(Structure):
    _fields_ = (
        ("header", vfio_info_cap_header),
        ("type", c_uint32),                # global per bus driver
        ("subtype", c_uint32),             # type specific
    )

class vfio_region_info(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
        ("index", c_uint32),       # Region index
        ("cap_offset", c_uint32),  # Offset within info struct of first cap
        ("size", c_uint64),        # Region size (bytes)
        ("offset", c_uint64),      # Region offset from start of device fd
    )

VFIO_REGION_INFO_FLAG_READ  = 1 << 0  # Region supports read
VFIO_REGION_INFO_FLAG_WRITE = 1 << 1  # Region supports write
VFIO_REGION_INFO_FLAG_MMAP  = 1 << 2  # Region supports mmap
VFIO_REGION_INFO_FLAG_CAPS  = 1 << 3  # Info supports caps

class vfio_irq_info(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
        ("index", c_uint32),  # IRQ index
        ("count", c_uint32),  # Number of IRQs within this index
    )

VFIO_IRQ_INFO_EVENTFD    = 1 << 0
VFIO_IRQ_INFO_MASKABLE   = 1 << 1
VFIO_IRQ_INFO_AUTOMASKED = 1 << 2
VFIO_IRQ_INFO_NORESIZE   = 1 << 3

VFIO_DEVICE_GET_IRQ_INFO = _IO(VFIO_TYPE, VFIO_BASE + 9)

VFIO_DEVICE_SET_IRQS = _IO(VFIO_TYPE, VFIO_BASE + 10)

VFIO_DEVICE_RESET = _IO(VFIO_TYPE, VFIO_BASE + 11)

# This is an example, actual format must be defined at runtime.
class vfio_irq_set_data(Array):
    _type_ = c_uint8
    _length_ = 16  # actual length is `count` below

class vfio_irq_set(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
        ("index", c_uint32),
        ("start", c_uint32),
        ("count", c_uint32),
        ("data", vfio_irq_set_data),
    )

VFIO_IRQ_SET_DATA_NONE      = 1 << 0  # Data not present
VFIO_IRQ_SET_DATA_BOOL      = 1 << 1  # Data is bool (u8)
VFIO_IRQ_SET_DATA_EVENTFD   = 1 << 2  # Data is eventfd (s32)
VFIO_IRQ_SET_ACTION_MASK    = 1 << 3  # Mask interrupt
VFIO_IRQ_SET_ACTION_UNMASK  = 1 << 4  # Unmask interrupt
VFIO_IRQ_SET_ACTION_TRIGGER = 1 << 5  # Trigger interrupt

VFIO_IRQ_SET_DATA_TYPE_MASK = (
    VFIO_IRQ_SET_DATA_NONE
  | VFIO_IRQ_SET_DATA_BOOL
  | VFIO_IRQ_SET_DATA_EVENTFD
)
VFIO_IRQ_SET_ACTION_TYPE_MASK = (
    VFIO_IRQ_SET_ACTION_MASK
  | VFIO_IRQ_SET_ACTION_UNMASK
  | VFIO_IRQ_SET_ACTION_TRIGGER
)

VFIO_IOMMU_GET_INFO = _IO(VFIO_TYPE, VFIO_BASE + 12)

class vfio_iommu_type1_info(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
        ("iova_pgsizes", c_uint64),  # Bitmap of supported page sizes
    )

VFIO_IOMMU_INFO_PGSIZES = 1 << 0

VFIO_IOMMU_MAP_DMA = _IO(VFIO_TYPE, VFIO_BASE + 13)

class vfio_iommu_type1_dma_map(Structure):
    _fields_ = (
        ("argsz", c_uint32),
        ("flags", c_uint32),
        ("vaddr", c_uint64),  # Process virtual address
        ("iova", c_uint64),  # IO virtual address
        ("size", c_uint64),  # Size of mapping (bytes)
    )

VFIO_DMA_MAP_FLAG_READ = 1 << 0   # readable from device
VFIO_DMA_MAP_FLAG_WRITE = 1 << 1  # writable from device

# end of vfio.h

def main():
    print("getting IOMMU groups of PCI(e) devices")

    grp2devs = defaultdict(list)

    pci_devs_pfx = join("/", "sys", "bus", "pci", "devices")

    for dev_dir in listdir(pci_devs_pfx):
        iommu_grp_path = join(pci_devs_pfx, dev_dir, "iommu_group")
        if not exists(iommu_grp_path):
            print("%s is not in a IOMMU group" % dev_dir)
            continue

        grp_link_path = readlink(iommu_grp_path)
        grp = basename(grp_link_path)

        print("%s is in group %s" % (dev_dir, grp))

        insort(grp2devs[grp], dev_dir)

    if not exists(vfio_path):
        print("no " + vfio_path)
        return 1

    print("opening " + vfio_path)
    container_fd = libc_open(b_vfio_path, O_RDWR)
    print("containerfd = " + str(container_fd))

    if container_fd < 0:
        print("error opening " + vfio_path)
        return container_fd

    c_container_fd = c_uint32(container_fd)

    vfio_api_version = libc_ioctl(container_fd, VFIO_GET_API_VERSION)
    print("vfio_api_version = " + str(vfio_api_version))

    print("getting API version")
    if vfio_api_version != VFIO_API_VERSION:
        print("unexpected API version")
        return 2

    print("checking VFIO_TYPE1_IOMMU extension")
    if not libc_ioctl(container_fd, VFIO_CHECK_EXTENSION, VFIO_TYPE1_IOMMU):
        print("VFIO does not support IOMMU driver")
        return 3

    # virtual phisical memory for devices
    vmem = create_string_buffer(1 << 20)

    print("handling IOMMU groups")
    for grp in listdir(vfio_pfx):
        if not re_iommu_grp.match(grp):
            continue

        grp_path = join(vfio_pfx, grp)
        print("found group %s: %s" % (grp, grp_path))

        b_grp_path = grp_path.encode("utf-8")

        print("opening " + grp_path)
        grp_fd = libc_open(b_grp_path, O_RDWR)

        print("grp_fd = " + str(grp_fd))

        if grp_fd < 0:
            print("error opening " + grp_path)
            return grp_fd

        grp_status = vfio_group_status()
        grp_status.argsz = sizeof(vfio_group_status)

        print("getting group status")
        rc = libc_ioctl(grp_fd, VFIO_GROUP_GET_STATUS, byref(grp_status))

        if rc:
            print("ioctl VFIO_GROUP_GET_STATUS failed")
            return rc

        flags = grp_status.flags
        print("VIABLE = "
            + str(bool(flags & VFIO_GROUP_FLAGS_VIABLE))
        )
        print("CONTAINER_SET = "
            + str(bool(flags & VFIO_GROUP_FLAGS_CONTAINER_SET))
        )

        try:
            if not (flags & VFIO_GROUP_FLAGS_VIABLE):
                print("group is not viable, skipping")
                continue

            if flags & VFIO_GROUP_FLAGS_CONTAINER_SET:
                print("group is already added to a container, skipping")
                continue

            print("adding group %s to container" % grp)
            rc = libc_ioctl(
                grp_fd,
                VFIO_GROUP_SET_CONTAINER,
                byref(c_container_fd)
            )

            if rc:
                print("failed to set container for the group: " + str(rc))
                return rc

            try:
                print("enabling TYPE1 IOMMU model")
                rc = libc_ioctl(
                    container_fd,
                    VFIO_SET_IOMMU,
                    VFIO_TYPE1_IOMMU
                )
                if rc:
                    print("failed to enable TYPE1 IOMMU model: " + str(rc))
                    return rc

                print("getting IOMMU info")

                iommu_info = vfio_iommu_type1_info(
                    argsz = sizeof(vfio_iommu_type1_info)
                )

                rc = libc_ioctl(
                    container_fd,
                    VFIO_IOMMU_GET_INFO,
                    byref(iommu_info)
                )

                if rc:
                    print("failed to get IOMMU info: " + str(rc))
                    return rc

                flags = iommu_info.flags
                if flags & VFIO_IOMMU_INFO_PGSIZES:
                    iova_pgsizes = iommu_info.iova_pgsizes
                    print("Bitmap of supported page sizes: 0x%016x" % (
                        iova_pgsizes
                    ))

                    # It's known that virtual address for DMA mapping must
                    # ba aligned.
                    # I hope that, alignment must be at least as minimum
                    # mapping page size.
                    # TODO: find a reference in the kernel docs
                    #       and provide a the link

                    min_pg_size = (iova_pgsizes & -iova_pgsizes)

                    # trailing_zeros
                    tz = min_pg_size - 1

                    # at least one full page must be in our buffer
                    assert (min_pg_size << 1) <= sizeof(vmem)

                    vmem_base = addressof(vmem)

                    vaddr = (vmem_base + min_pg_size) & ~tz

                    voffset = vaddr - vmem_base

                    vsize = (sizeof(vmem) - voffset) & ~tz

                print(
                    (
                        "setup DMA mapping"
                        ": 0 at: 0x%016x"
                        ", size: 0x%x"
                        ", offset: 0x%x"
                    ) % (
                        vaddr,
                        vsize,
                        voffset,
                    )
                )

                dma_map = vfio_iommu_type1_dma_map(
                    argsz = sizeof(vfio_iommu_type1_dma_map),\
                    vaddr = vaddr,
                    size = vsize,
                    iova = 0,  # starting at 0x0 from device view
                    flags = VFIO_DMA_MAP_FLAG_READ | VFIO_DMA_MAP_FLAG_WRITE,
                )

                rc = libc_ioctl(
                    container_fd,
                    VFIO_IOMMU_MAP_DMA,
                    byref(dma_map)
                )

                if rc:
                    print("failed to setup DMA mapping: " + str(rc))
                    return rc

                print("handling devices in group " + str(grp))

                for dev_name in grp2devs[grp]:
                    print("handling " + dev_name)

                    b_dev_name = dev_name.encode("utf-8")

                    dev_fd = libc_ioctl(
                        grp_fd,
                        VFIO_GROUP_GET_DEVICE_FD,
                        b_dev_name
                    )

                    print("dev_fd = " + str(dev_fd))

                    if dev_fd < 0:
                        print("failed to get dev_fd")
                        return dev_fd

                    try:
                        rc = _handle_device(**locals())
                        if rc:
                            return rc
                    finally:
                        print("closing dev_fd")
                        rc = libc_close(dev_fd)
                        if rc:
                            print("failed to close dev_fd: " + str(rc))
                            return rc
            finally:
                print("removing group %s from container" % grp)
                rc = libc_ioctl(
                    grp_fd,
                    VFIO_GROUP_UNSET_CONTAINER
                )
                if rc:
                    print("failed to unset coutainer of the group: " + str(rc))
                    return rc

        finally:
            print("closing grp_fd")
            rc = libc_close(grp_fd)

            if rc:
                print("failed to close grp_fd: " + str(rc))
                return rc

    print("closing container_fd")
    rc = libc_close(container_fd)
    if rc:
        print("failed to close container_fd: " + str(rc))
        return rc


def _handle_device(dev_fd, **ctx):
    print("getting device info")

    dev_info = vfio_device_info(
        argsz = sizeof(vfio_device_info),
    )

    rc = libc_ioctl(
        dev_fd,
        VFIO_DEVICE_GET_INFO,
        byref(dev_info)
    )

    if rc:
        print("failed to get device info: " + str(rc))
        return rc

    flags = dev_info.flags

    print("flags:")

    if flags & VFIO_DEVICE_FLAGS_RESET:
        print(" | RESET")
        support_resert = True
    else:
        support_resert = False

    if flags & VFIO_DEVICE_FLAGS_PLATFORM:
        print(" | PLATFORM")
    if flags & VFIO_DEVICE_FLAGS_AMBA:
        print(" | AMBA")
    if flags & VFIO_DEVICE_FLAGS_CCW:
        print(" | CCW")
    if flags & VFIO_DEVICE_FLAGS_AP:
        print(" | AP")

    if flags & VFIO_DEVICE_FLAGS_PCI:
        print(" | PCI")
    else:
        print("it's not a vfio-pci device, skipping")
        return

    print("num_regions = " + str(dev_info.num_regions))
    print("num_irqs = " + str(dev_info.num_irqs))

    print("getting regions infos")

    reg_infos = []

    for i in range(dev_info.num_regions):
        print("getting info of region " + str(i))
        reg_info = vfio_region_info(
            argsz = sizeof(vfio_region_info),
            index = i,
        )

        rc = libc_ioctl(dev_fd, VFIO_DEVICE_GET_REGION_INFO, byref(reg_info))
        if rc:
            print("failed to get region info: " + str(rc))
            if i == VFIO_PCI_CONFIG_REGION_INDEX:
                return rc
            else:
                reg_info = None
                continue  # not critical

        reg_infos.append(reg_info)

        print("flags     :")
        flags = reg_info.flags
        if flags & VFIO_REGION_INFO_FLAG_READ:
            print(" | READ")
        if flags & VFIO_REGION_INFO_FLAG_WRITE:
            print(" | WRITE")
        if flags & VFIO_REGION_INFO_FLAG_MMAP:
            print(" | MMAP")
        if flags & VFIO_REGION_INFO_FLAG_CAPS:
            print(" | CAPS")
            has_caps = True
        else:
            has_caps = False

        print("cap_offset: " + str(reg_info.cap_offset))
        print("size      : " + hex(reg_info.size))
        print("offset    : " + hex(reg_info.offset))

        if has_caps:
            # TODO:
            #  - check argsz for required dev_info size
            #  - allocate new buffer of that size
            #  - parse chain of vfio_info_cap_header starting from cap_offset
            #  - print headers
            #  - print known cap formats:
            #    - vfio_region_info_cap_sparse_mmap
            #    - vfio_region_info_cap_type
            pass

    print("getting IRQs infos")

    irq_infos = []

    for i in range(dev_info.num_irqs):
        print("getting info of IRQ " + str(i))

        irq_info = vfio_irq_info(
            argsz = sizeof(vfio_irq_info),
            index = i,
        )

        rc = libc_ioctl(dev_fd, VFIO_DEVICE_GET_IRQ_INFO, byref(irq_info))
        if rc:
            print("failed to get IRQ info: " + str(rc))
            # return rc
            continue  # not critical

        irq_infos.append(irq_info)

        flags = irq_info.flags
        print("flags:")
        if flags & VFIO_IRQ_INFO_EVENTFD:
            print(" | EVENTFD")
        if flags & VFIO_IRQ_INFO_MASKABLE:
            print(" | MASKABLE")
        if flags & VFIO_IRQ_INFO_AUTOMASKED:
            print(" | AUTOMASKED")
        if flags & VFIO_IRQ_INFO_NORESIZE:
            print(" | NORESIZE")
        print("count: " + str(irq_info.count))

    print("reading device IDs")

    conf_space_reg = reg_infos[VFIO_PCI_CONFIG_REGION_INDEX]
    conf_space_offset = conf_space_reg.offset

    print("pread-ing Device/Vendor IDs")
    c_did_vid = c_uint32()
    rc = libc_pread(
        dev_fd,
        byref(c_did_vid),
        c_size_t(sizeof(c_did_vid)),
        c_off_t(conf_space_offset + PCI_DID_VID_OFFSET)
    )

    if rc != sizeof(c_did_vid):
        print("filed to pread Device/Vendor IDs: " + str(rc))
        return rc

    did_vid = c_did_vid.value
    print("Device ID: 0x%04x, Vendor ID: 0x%04x" % (
        did_vid >> 16, did_vid & 0xFFFF
    ))

    print("pread-ing class & revision")
    c_cls_rev = c_uint32()
    rc = libc_pread(
        dev_fd,
        byref(c_cls_rev),
        c_size_t(sizeof(c_cls_rev)),
        c_off_t(conf_space_offset + PCI_CLASS_REV_OFFSET)
    )

    if rc != sizeof(c_cls_rev):
        print("filed to pread class & revision: " + str(rc))
        return rc

    cls_rev = c_cls_rev.value
    print("Class: 0x%06x, Revision: 0x%02x" % (
        cls_rev >> 8, cls_rev & 0xFF
    ))

    print("trying to find a mmap-able BAR and dump its part")
    for i, bar in enumerate(reg_infos):
        if not (bar.flags & VFIO_REGION_INFO_FLAG_MMAP):
            continue

        if i > VFIO_PCI_BAR5_REGION_INDEX:
            # no mmap-able BARs
            break

        print("mmap-ing BAR" + str(i))

        prot = 0
        if bar.flags & VFIO_DMA_MAP_FLAG_READ:
            prot |= PROT_READ
        if bar.flags & VFIO_DMA_MAP_FLAG_WRITE:
            prot |= PROT_WRITE

        bar_vaddr = libc_mmap(
            0,
            bar.size,
            prot,
            MAP_SHARED,
            dev_fd,
            bar.offset
        )
        print("bar_vaddr = " + hex(bar_vaddr))

        if bar_vaddr == c_void_p(-1).value:
            err = cast(libc_errno, c_p_int).contents.value
            print("failed to mmap configuration space: "
                + str(err)
            )
            return err

        dots = False

        print("dumping beginning of BAR" + str(i))
        print(" %16s : %8s | %-13s" % ("offset", "hex", "dec"))
        for o in range(0, min(bar.size, 0x300), 4):
            dword_vaddr = bar_vaddr + o
            c_p_dword = cast(dword_vaddr, c_p_uint32)
            val = c_p_dword.contents.value

            if val:
                print(" %16x : %08x | %-13d" % (o, val, val))
                dots = False
            else:
                if not dots:
                    dots = True
                    print("              ... : < zeros >")

        print("munmap-ing BAR" + str(i))
        rc = libc_munmap(c_void_p(bar_vaddr), c_off_t(bar.size))
        if rc:
            print("failed to munmap the BAR: " + str(rc))
            return rc

        # dump only one BAR
        break
    else:
        print("no mmap-able BARs found")

    if support_resert:
        print("resetting device")
        rc = libc_ioctl(dev_fd, VFIO_DEVICE_RESET)

        if rc:
            print("failed to reset device: " + str(rc))
            return rc

if __name__ == "__main__":
    exit(main() or 0)
