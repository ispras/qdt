from source import \
    Source, \
    Header, \
    Structure, \
    TypeNotRegistered, \
    Initializer, \
    Function, \
    Macro, \
    Type

from os.path import \
    join

# properties
class QOMPropertyType(object):
    set_f = None
    build_val = None

class QOMPropertyTypeLink(QOMPropertyType):
    set_f = "object_property_set_link"

class QOMPropertyTypeString(QOMPropertyType):
    set_f = "object_property_set_str"

class QOMPropertyTypeBoolean(QOMPropertyType):
    set_f = "object_property_set_bool"

class QOMPropertyTypeInteger(QOMPropertyType):
    set_f = "object_property_set_int"

    @staticmethod
    def build_val(prop_val):
        if Type.exists(prop_val):
            return str(prop_val)
        return "0x%0x" % prop_val

class QOMPropertyValue(object):
    def __init__(self,
        prop_type,
        prop_name,
        prop_val
        ):
        self.prop_type = prop_type
        self.prop_name = prop_name
        self.prop_val = prop_val

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

type2vmstate = {
    "PCIDevice" : "VMSTATE_PCI_DEVICE"
}

class QOMType(object):
    def __init__(self, name):
        self.qtn = QemuTypeName(name)
        self.struct_name = "{}State".format(self.qtn.for_struct_name)
        self.state_fields = []

    def add_state_fields(self, fields):
        for field in fields:
            self.add_state_field(field)

    def add_state_field(self, field):
        field.prop_macro_name = self.qtn.for_macros + "_" + field.name.upper()
        self.state_fields.append(field)

    def add_state_field_h(self, type_name, field_name,
            num = None,
            save = True,
            prop = False,
            default = None
        ):
        t = Type.lookup(type_name)
        f = QOMStateField(t, field_name,
            num = num,
            save = save,
            prop = prop,
            default = default
        )
        self.add_state_field(f)

    def gen_state(self):
        s = Structure(self.qtn.for_struct_name + 'State')
        for f in self.state_fields:
            s.append_field(f.type.gen_var(f.name, array_size = f.num))
        return s

    def gen_property_macros(self, source):
        for field in self.state_fields:
            if not field.prop:
                continue

            t = Macro(field.prop_macro_name, text = field.prop_name)
            source.add_type(t)

    def gen_vmstate_initializer(self, state_struct):
        type_macro = Type.lookup("TYPE_" + self.qtn.for_macros)
        code = ("""{
    .name = %s,
    .version_id = 1,
    .fields = (VMStateField[]) {""" % type_macro.name
        )

        # TODO: make Macro hashable, then use set()
        used_macros = {}
        global type2vmstate

        first = True
        for f in self.state_fields:
            if not f.save:
                continue

            if f.num is not None:
                raise Exception(
                    "VMState field generation for arrays is not supported"
                )

            try:
                vms_macro_name = type2vmstate[f.type.name]
            except KeyError:
                raise Exception(
                    "VMState generation for type %s is not implemented" % \
                        f.type.name
                )

            vms_macro = Type.lookup(vms_macro_name)
            used_macros[vms_macro_name] = vms_macro

            init = Initializer(
                # code of macro initializer is dict
                {
                    "_field": f.name,
                    "_state": state_struct.name
                }
            )

            if first:
                first = False
                code += "\n"
            else:
                code += ",\n"

            code += " " * 8 + vms_macro.gen_usage_string(init)

        # Generate VM state list terminator macro.
        if first:
            code += "\n"
        else:
            code += ",\n"
        code += " " * 8 + Type.lookup("VMSTATE_END_OF_LIST").gen_usage_string()

        code += "\n    }\n}"

        init = Initializer(
            code = code,
            used_types = [
                type_macro,
                Type.lookup("VMStateField"),
                state_struct
            ] + used_macros.values()
        )
        return init

    def gen_vmstate_var(self, state_struct):
        init = self.gen_vmstate_initializer(state_struct)

        vmstate = Type.lookup("VMStateDescription").gen_var(
            name = "vmstate_%s" % self.qtn.for_id_name,
            static = True,
            initializer = init
        )

        return vmstate

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


class QOMStateField(object):
    def __init__(self, ftype, name,
            num = None,
            save = True,
            prop = False,
            default = None
        ):
        self.type = ftype
        self.name = name
        self.num = num
        self.prop_name = '"' + name.replace('_', '-') + '"'
        self.save = save
        self.prop = prop
        self.default = default

class QOMDevice(QOMType):
    def __init__(self, name, directory):
        super(QOMDevice, self).__init__(name)

        self.directory = directory

        # Define header file
        header_path = join("hw", directory, self.qtn.for_header_name + ".h")
        try:
            self.header = Header.lookup(header_path)
        except Exception:
            self.header = Header(header_path)

        # Define source file
        source_path = join("hw", directory, self.qtn.for_header_name + ".c")
        self.source = Source(source_path)

    def gen_source(self):
        pass

