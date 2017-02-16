from source import \
    TypeNotRegistered, \
    Initializer, \
    Function, \
    Type

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

    def gen_instance_init_name(self):
        return "%s_instance_init" % self.qtn.for_id_name

    def gen_register_types_name(self):
        return "%s_register_types" % self.qtn.for_id_name

    def gen_type_info_name(self):
        return "%s_info" % self.qtn.for_id_name

    def gen_instance_init_fn(self, state_struct,
        code = "",
        s_is_used = False,
        used_types = [],
        used_globals = []
    ):
        type_cast_macro = Type.lookup(self.qtn.for_macros)

        fn = Function(
            name = self.gen_instance_init_name(),
            body = """\
    {used}{Struct} *s = {UPPER}(obj);
{extra_code}\
""".format(
    Struct = state_struct.name,
    UPPER = type_cast_macro.name,
    extra_code = code,
    used = "" if s_is_used else "__attribute__((unused)) "
            ),
            static = True,
            args = [
                Type.lookup("Object").gen_var("obj", pointer = True)
            ],
            used_types = [state_struct, type_cast_macro] + used_types,
            used_globals = used_globals
        )

        return fn

    def gen_type_info_var(self, state_struct, instance_init_fn, class_init_fn,
        parent_tn = "TYPE_OBJECT"
    ):
        used_types = [
            state_struct,
            instance_init_fn,
            class_init_fn
        ]

        try:
            parent_macro = Type.lookup(parent_tn)
        except TypeNotRegistered:
            parent_macro = None
        else:
            used_types.append(parent_macro)

        # Type info initializer
        tii = Initializer(
            code = """{{
    .name          = TYPE_{UPPER},
    .parent        = {parent_tn},
    .instance_size = sizeof({Struct}),
    .instance_init = {instance_init},
    .class_init    = {class_init}
}}""".format(
    UPPER = self.qtn.for_macros,
    parent_tn = ('"%s"' % parent_tn) if parent_macro is None \
                else parent_macro.name,
    Struct = state_struct.name,
    instance_init = instance_init_fn.name,
    class_init = class_init_fn.name
            ),
            used_types = used_types
        )
        # TypeInfo variable
        tiv = Type.lookup("TypeInfo").gen_var(
            name = self.gen_type_info_name(),
            static = True,
            initializer = tii
        )

        return tiv

    def gen_register_types_fn(self, *infos):
        body = ""
        for info in infos:
            body += "    type_register_static(&%s);\n" % info.name

        fn = Function(
            name = self.gen_register_types_name(),
            body = body,
            static = True,
            used_types = [
                Type.lookup("type_register_static")
            ],
            used_globals = list(infos)
        )

        return fn

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
