import json

from source import \
    Type, \
    Header, \
    Macro

class QemuTypeName(object):
    def __init__(self, name):
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value.strip()

        lower_name = self._name.lower();
        tmp = '_'.join(lower_name.split())
        tmp = '_'.join(tmp.split('-'))
        tmp = ''.join(tmp.split('/'))

        self.for_id_name = tmp
        self.for_header_name = tmp

        tmp =''.join(self._name.split())
        tmp =''.join(tmp.split('/'))
        tmp =''.join(tmp.split('-'))
        self.for_struct_name = tmp

        upper_name = self._name.upper()
        tmp = '_'.join(upper_name.split())
        tmp = '_'.join(tmp.split('-'))
        tmp = ''.join(tmp.split('/'))

        self.for_macros = tmp


class QOMType(object):
    def __init__(self, name):
        self.qtn = QemuTypeName(name)

    def gen_register_types_name(self):
        return "%s_register_types" % self.qtn.for_id_name

    def gen_type_info_name(self):
        return "%s_info" % self.qtn.for_id_name

    @staticmethod
    def gen_mmio_read(name, struct_name, type_cast_macro):
        return Type.lookup("MemoryRegionOps_read").use_as_prototype(
            name = name,
            static = True,
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(opaque);
    uint64_t ret = 0;

    switch (addr) {{
    default:
        printf("%s: unimplemented read from 0x%"HWADDR_PRIx", size %d\\n",
            __FUNCTION__, addr, size);
        break;
    }}

    return ret;
""".format(
    Struct = struct_name,
    UPPER = type_cast_macro
),
        used_types = [
            Type.lookup("uint64_t"),
            Type.lookup("printf"),
            Type.lookup("HWADDR_PRIx")
        ]
        )

    @staticmethod
    def gen_mmio_write(name, struct_name, type_cast_macro):
        return Type.lookup("MemoryRegionOps_write").use_as_prototype(
            name = name,
            static = True,
            body = """\
    __attribute__((unused)) {Struct} *s = {UPPER}(opaque);

    switch (addr) {{
    default:
        printf("%s: unimplemented write to 0x%"HWADDR_PRIx", size %d, "
                "value 0x%"PRIx64"\\n", __FUNCTION__, addr, size, data);
        break;
    }}
""".format(
    Struct = struct_name,
    UPPER = type_cast_macro
),
            used_types = [
                Type.lookup("uint64_t"),
                Type.lookup("printf"),
                Type.lookup("HWADDR_PRIx"),
                Type.lookup("PRIx64")
            ]
        )
