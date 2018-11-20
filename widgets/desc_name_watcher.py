__all__ = [
    "DescNameWatcher"
]

from qemu import (
    DOp_SetAttr,
    QOMDevice,
    MachineNode,
    DeviceNode,
    MOp_SetDevQOMType,
    QemuTypeName
)
from inspect import (
    getmro
)
from common import (
    mlget as _
)


class DescNameWatcher(object):
    """ Watches operations on QOM description names and performs automatic
refactoring:
    - updates QOM type of devices in machines when the corresponding device
      template name is changed.
    """

    def __init__(self, gpht):
        """
    :type gpht: GUIProjectHistoryTracker
        """

        self.gpht = gpht
        self.p = gpht.p
        gpht.watch_changed(self._on_changed)

    def _on_changed(self, op):
        if not isinstance(op, DOp_SetAttr):
            return
        if op.attr != "name":
            return
        desc = op.find_desc()
        if QOMDevice not in getmro(desc.__qom_template__):
            return

        prev_name = op.old_val if op.done else op.val
        prev_type = QemuTypeName(prev_name).type_macro
        new_type = QemuTypeName(desc.name).type_macro

        seq = self.gpht.begin()

        for mach in self.p.descriptions:
            if not isinstance(mach, MachineNode):
                continue

            for nid, node in mach.id2node.items():
                if not isinstance(node, DeviceNode):
                    continue

                if node.qom_type != prev_type:
                    continue
                seq.stage(MOp_SetDevQOMType, new_type, nid, mach.__sn__)

        seq.commit(
            sequence_description = _(
                "Automatic update of QOM type for devices in all machines."
            )
        )
