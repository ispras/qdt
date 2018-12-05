__all__ = [
    "GUILayout"
]

from copy import (
    deepcopy
)
from qemu import (
    QemuTypeName
)
from common import (
    same_attrs
)


class GUILayout(object):
    def __init__(self, desc_name, opaque, shown = None):
        self.desc_name = desc_name
        self.opaque = opaque
        # ID of the layout
        self.lid = None;
        # cached widget reference
        self.widget = None

        try:
            (self.opaque.__gen_code__)
        except AttributeError:
            pass
        else:
            # Serializable object in opaque, no legacy compatibility is needed.
            self.shown = True if shown is None else shown
            return

        # Legacy formats compatibility.
        try:
            cfg = self.opaque[-1]
        except KeyError:
            self.shown = shown if shown is not None else True
        else:
            try:
                self.shown = cfg["shown"]
            except KeyError:
                self.shown = shown if shown is not None else True
            else:
                del cfg["shown"]

            if not cfg.values():
                # remove empty configuration
                del self.opaque[-1]

    def __same__(self, o):
        if type(self) is not type(o):
            return False

        if same_attrs(self, o, "desc_name", "shown", "opaque"):
            return True
        return False

    def __deepcopy__(self, memo):
        ret = type(self)(self.desc_name, deepcopy(self.opaque, memo))
        ret.lid = self.lid
        return ret

    def sync_from_widget(self):
        if self.widget:
            self.opaque = self.widget.gen_layout()

    def __dfs_children__(self):
        try:
            (self.opaque.__gen_code__)
        except AttributeError:
            return []
        else:
            return [self.opaque]

    def __var_base__(self):
        return "%s_l%s" % (
            QemuTypeName(self.desc_name).for_header_name,
            "" if self.lid is None else self.lid
        )

    def __gen_code__(self, g):
        g.reset_gen(self)
        g.gen_field("desc_name = " + g.gen_const(self.desc_name))
        g.gen_field("opaque = ")
        g.pprint(self.opaque)
        g.gen_field("shown = " + g.gen_const(self.shown))
        g.gen_end()

        if self.lid is not None:
            g.line(g.nameof(self) + ".lid = " + g.gen_const(self.lid))
