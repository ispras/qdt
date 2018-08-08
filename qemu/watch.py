__all__ = [
    "q_event_dict",
    "q_event_list"
]

from gdb import (
    Break
)
from inspect import (
    isclass,
    getmro
)

# Events are valid for this QEMU version
# 4743c23509a51bd4ee85cc272287a41917d1be35
# v2.12.0


class TypeRegister(Break):
    """ object.c:139

    type_register_internal
    """

    def __top_half__(self, runtime):
        self.type_impl = runtime["ti"].dereference().to_global()


class QOMModuleReady(Break):
    """ vl.c:3075

    main, just after QOM module initialization
    """


class ObjectInitStarted(Break):
    """ object.c:384

    object_initialize_with_type
    """

    def __top_half__(self, runtime):
        self.type_impl = runtime["type"].dereference().to_global()
        self.object = runtime["obj"].dereference().to_global()


class ObjectInitEnded(Break):
    """ object.c:386

    object_initialize_with_type
    """

    def __top_half__(self, runtime):
        self.object = runtime["obj"].dereference().to_global()


class MachineInitStarted(Break):
    """ hw/core/machine.c:829

    machine_run_board_init
    """

    def __top_half__(self, runtime):
        self.machine = runtime["machine"].dereference().to_global()


class MachineInitEnded(Break):
    """ hw/core/machine.c:830

    machine_run_board_init
    """

    def __top_half__(self, runtime):
        self.machine = runtime["machine"].dereference().to_global()


class MemoryInit(Break):
    """ memory.c:1153

    return from memory_region_init
    """

    def __top_half__(self, runtime):
        self.memory = runtime["mr"].dereference().to_global()


class AddProperty(Break):
    """ object.c:976

    return from object_property_add
    """


class SetProperty(Break):
    """ object.c:1122

    object_property_set (prop. exists and has a setter)
    """


class BusRealize(Break):
    """ hw/core/bus.c:105

    qbus_realize, if parent is not NULL
    """


class DetachBus(Break):
    """ "hw/core/bus.c:123

    bus_unparent, before actual unparanting
    """


class AttachDevice(Break):
    """ hw/core/qdev.c:73

    bus_add_child, a device is attached to a bus
    """

class DetachDevice(Break):
    """ hw/core/qdev.c:57

    bus_remove_child, before actual unparanting
    """


breaks = {}

for name, ref in globals().items():
    if not isclass(ref):
        continue
    if ref is Break:
        continue
    if Break not in getmro(ref):
        continue

    breaks[name] = ref

__all__.extend(breaks.keys())

q_event_list = [cls() for cls in breaks.values()]

q_event_dict = {}

for e in q_event_list:
    q_event_dict[e.description] = e
