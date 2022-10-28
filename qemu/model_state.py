__all__ = [
    "StateStruct"
]

from source import (
    Initializer,
    Structure,
    Type,
)


class StateStruct(object):

    def __init__(self, c_type_name, *fields, **kw):
        self.vmsd_min_version_id = kw.pop("vmsd_min_version_id", None)
        self.vmsd_version_id = kw.pop("vmsd_version_id", 1)
        self.vmsd_state_name = kw.pop("vmsd_state_name", None)

        self.c_type_name = c_type_name
        self.fields = []
        for field in fields:
            self.add_field(field)

    def add_field(self, field):
        "`field` is of `QOMTypeStateField`"
        self.fields.append(field)

    def gen_c_type(self):
        s = Structure(self.c_type_name,
            origin = self,
        )
        for f in self.fields:
            s.append_field(Type[f.c_type_name](
                f.name,
                array_size = f.array_size,
            ))
        return s

    def gen_vmstate_initializer(self, name):
        lines = []
        l = lines.append
        l("{")
        l('    .name@b=@s"' + name + '",')
        if self.vmsd_version_id is not None:
            l("    .version_id@b=@s%d," % self.vmsd_version_id)
        if self.vmsd_min_version_id is not None:
            l("    .minimum_version_id@b=@s%d," % self.vmsd_min_version_id)
        l("    .fields@b=@s(VMStateField[])@b{")

        used_macros = set()
        global type2vmstate

        for f in self.fields:
            if not f.save_in_vmsd:
                continue

            # code of macro initializer is dict
            fdict = {
                "_f": f.name,
                "_s": self.c_type_name,
                # Macros may use different argument names
                "_field": f.name,
                "_state": self.c_type_name
            }

            try:
                vms_macro_name = type2vmstate[f.c_type_name]
            except KeyError:
                raise Exception(
                    "VMState generation for type %s is not implemented" % \
                        f.c_type_name
                )

            if f.array_size is not None:
                vms_macro_name += "_ARRAY"
                fdict["_n"] = str(f.array_size)

            vms_macro = Type[vms_macro_name]
            used_macros.add(vms_macro)

            l(" " * 8 + vms_macro.gen_usage_string(Initializer(fdict)) + ",")

        # Generate VM state list terminator macro.
        vms_macro = Type["VMSTATE_END_OF_LIST"]
        used_macros.add(vms_macro)
        l(" " * 8 + vms_macro.gen_usage_string())
        l("    }")
        l("}")

        init = Initializer(
            code = "\n".join(lines),
            used_types = used_macros.union([
                Type["VMStateField"],
                Type[self.c_type_name],
            ])
        )
        return init

    def gen_vmstate_var(self,
        name_suffix,
        state_name = None,
        **var_kw
    ):
        if state_name is None:
            state_name = self.vmsd_state_name or name_suffix
        name = "vmstate_" + name_suffix

        var_kw.setdefault("static", True)
        var_kw.setdefault("const", True)

        var = Type["VMStateDescription"](
            name = name,
            initializer = self.gen_vmstate_initializer(state_name),
            **var_kw
        )
        return var


type2vmstate = {
    "QEMUTimer*" : "VMSTATE_TIMER_PTR",
    "PCIDevice" : "VMSTATE_PCI_DEVICE"
}

for U in ["", "U"]:
    for bits in ["8", "16", "32", "64"]:
        # macro suffix
        msfx = U + "INT" + bits
        # C type name
        ctn = msfx.lower() + "_t"

        type2vmstate[ctn] = "VMSTATE_" + msfx
