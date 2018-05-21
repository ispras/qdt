__all__ = [
    "QOMPropertyType"
      , "QOMPropertyTypeLink"
      , "QOMPropertyTypeString"
      , "QOMPropertyTypeBoolean"
      , "QOMPropertyTypeInteger"
  , "QOMPropertyValue"
  , "QOMStateField"
  , "QemuTypeName"
  , "QOMType"
      , "QOMDevice"
      , "QOMCPU"
]

from source import (
    line_origins,
    Source,
    Header,
    Structure,
    TypeNotRegistered,
    Initializer,
    Function,
    Macro,
    Pointer,
    Type
)
from os.path import (
    join
)
from six import (
    integer_types
)
from common import (
    mlget as _
)
from collections import (
    OrderedDict
)
from .version import (
    get_vp
)

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

def qtn_char(c):
    # low ["0"; "9"] middle0 ["A", "Z"] middle1 ["a"; "z"] high
    if c < "0":
        # low
        return False
    # ["0"; "9"] middle0 ["A", "Z"] middle1 ["a"; "z"] high
    if "z" < c:
        # high
        return False
    # ["0"; "9"] middle0 ["A", "Z"] middle1 ["a"; "z"]
    if c < "A":
        # ["0"; "9"] middle0
        return c <= "9"
    # ["A", "Z"] middle1 ["a"; "z"]
    if "Z" < c:
        # middle1 ["a"; "z"]
        return "A" <= c
    # ["A", "Z"]
    return True

# Replacements for characters
qtn_id_char_map = {
    "/" : ""
    # default : c if qtn_char(c) else "_"
}

qtn_struct_char_map = {
    # default : c if qtn_char(c) else ""
}

qtn_macro_char_map = qtn_id_char_map
# same default

class QemuTypeName(object):
    def __init__(self, name):
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value.strip()

        tmp = ""
        for c in self._name.lower():
            if c in qtn_id_char_map:
                tmp += qtn_id_char_map[c]
            else:
                tmp += c if qtn_char(c) else "_"

        self.for_id_name = tmp
        self.for_header_name = tmp

        tmp = ""
        for c in self._name:
            if c in qtn_struct_char_map:
                tmp += qtn_struct_char_map[c]
            else:
                tmp += c if qtn_char(c) else ""

        self.for_struct_name = tmp

        tmp = ""
        for c in self._name.upper():
            if c in qtn_macro_char_map:
                tmp += qtn_macro_char_map[c]
            else:
                tmp += c if qtn_char(c) else "_"

        self.for_macros = tmp

# Property declaration generation helpers

def gen_prop_declaration(field, decl_macro_name, state_struct,
    default_default = None
):
    decl_macro = Type.lookup(decl_macro_name)
    used_types = set([decl_macro])
    bool_true = Type.lookup("true")
    bool_false = Type.lookup("false")

    init_code = {
        "_f" : field.name,
        "_s" : state_struct,
    }

    if field.prop_macro_name is not None:
        init_code["_n"] = Type.lookup(field.prop_macro_name)
        init_code["_name"] = init_code["_n"]

    init_code["_state"] = init_code["_s"]
    init_code["_field"] = init_code["_f"]

    # _conf is name of argument of macro DEFINE_NIC_PROPERTIES that
    # corresponds to structure filed name
    init_code["_conf"] = init_code["_f"]

    if default_default is not None:
        if field.default is None:
            val = default_default
        else:
            val = field.default

        if isinstance(val, str):
            try:
                val_macro = Type.lookup(val)
            except TypeNotRegistered:
                val = '"%s"' % val
            else:
                val = val_macro
        elif isinstance(val, bool):
            if val:
                val = bool_true
            else:
                val = bool_false
        elif isinstance(val, integer_types):
            if field.type.name[0] == "u":
                val = "0x%X" % val
            else:
                val = str(val)
        else:
            val = str(val)

        init_code["_d"] = val
        init_code["_defval"] = val

    initializer = Initializer(code = init_code)
    usage_str = decl_macro.gen_usage_string(initializer)
    return (usage_str, used_types)

def declare_int(ctn, prop_macro):
    type2prop[ctn] = lambda field, state_struct: gen_prop_declaration(field,
        prop_macro, state_struct, default_default = 0
    )

type2prop = {
    "NICConf" : lambda field, state_struct: gen_prop_declaration(
        field, "DEFINE_NIC_PROPERTIES", state_struct
    ),
    "BlockBackend*" : lambda field, state_struct: gen_prop_declaration(
        field, "DEFINE_PROP_DRIVE", state_struct
    ),
    # before QEMU 2.7
    "CharDriverState*" : lambda field, state_struct: gen_prop_declaration(
        field, "DEFINE_PROP_CHR", state_struct
    ),
    # after QEMU 2.8
    "CharBackend" : lambda field, state_struct: gen_prop_declaration(
        field, "DEFINE_PROP_CHR", state_struct
    ),
    "bool" : lambda field, state_struct: gen_prop_declaration(field,
        "DEFINE_PROP_BOOL", state_struct, default_default = False
    ),
    "size_t" : lambda field, state_struct: gen_prop_declaration(field,
        "DEFINE_PROP_SIZE", state_struct, default_default = 0
    )
}

for U in ["", "U"]:
    for bits in ["8", "16", "32", "64"]:
        # macro suffix
        msfx = U + "INT" + bits
        # C type name
        ctn = msfx.lower() + "_t"

        declare_int(ctn, "DEFINE_PROP_" + msfx)

type2vmstate = {
    "QEMUTimer*" : "VMSTATE_TIMER_PTR",
    "PCIDevice" : "VMSTATE_PCI_DEVICE"
}

class QOMType(object):
    __attribute_info__ = OrderedDict([
        ("name", { "short": _("Name") })
    ])

    def __init__(self, name):
        self.qtn = QemuTypeName(name)
        self.struct_name = "{}State".format(self.qtn.for_struct_name)
        self.state_fields = []

    def test_basic_state(self):
        for u, bits in [("", "32"), ("u", "8"), ("u", "16"), ("u", "32"),
            ("u", "64")
        ]:
            # variable name
            ctn = u + "int" + bits + "_t"
            vn = "var_" + ctn
            self.add_state_field_h(ctn, vn, save = False,
                prop = True, default = (0xdeadbeef if bits == "32" else None)
            )

        self.add_state_field_h("size_t", "var_size", save = False, prop = True,
            default = "UINT32_MAX"
        )
        self.add_state_field_h("bool", "var_b0", save = False, prop = True)
        self.add_state_field_h("bool", "var_b1", save = False, prop = True,
            default = True
        )

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
            if field.prop_macro_name is None:
                continue

            t = Macro(field.prop_macro_name, text = field.prop_name)
            source.add_type(t)

    def gen_properties_initializer(self, state_struct):
        used_types = set()
        global type2prop

        code = "{"

        first = True
        for f in self.state_fields:
            if not f.prop:
                continue

            try:
                helper = type2prop[f.type.name]
            except KeyError:
                raise Exception(
                    "Property generation for type %s is not implemented" % \
                        f.type.name
                )

            decl_code, decl_types = helper(f, state_struct)

            used_types |= decl_types

            if first:
                first = False
                code += "\n"
            else:
                code += ",\n"
            code += "    " + decl_code

        # generate property list terminator
        terminator_macro = Type.lookup("DEFINE_PROP_END_OF_LIST")
        if first:
            code += "\n"
        else:
            code += ",\n"
        code += "    " + terminator_macro.gen_usage_string() + "\n}"

        init = Initializer(
            code = code,
            used_types = used_types.union([
                terminator_macro,
                state_struct
            ])
        )
        return init

    def gen_properties_global(self, state_struct):
        init = self.gen_properties_initializer(state_struct)
        prop_type = Type.lookup("Property")
        var = prop_type.gen_var(
            name = self.qtn.for_id_name + "_properties",
            initializer = init,
            static = True,
            array_size = 0
        )
        return var

    def gen_vmstate_initializer(self, state_struct):
        type_macro = Type.lookup("TYPE_" + self.qtn.for_macros)
        code = ("""{
    .name@b=@s%s,
    .version_id@b=@s1,
    .fields@b=@s(VMStateField[])@b{""" % type_macro.name
        )

        used_macros = set()
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
            used_macros.add(vms_macro)

            init = Initializer(
                # code of macro initializer is dict
                {
                    "_f": f.name,
                    "_s": state_struct.name,
                    # Macros may use different argument names
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
            used_types = used_macros.union([
                type_macro,
                Type.lookup("VMStateField"),
                state_struct
            ])
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

        total_used_types = set([state_struct, type_cast_macro])
        total_used_types.update(used_types)

        if self.timer_num > 0:
            total_used_types.update([
                Type.lookup("QEMU_CLOCK_VIRTUAL"),
                Type.lookup("timer_new_ns")
            ])
            s_is_used = True
            code += "\n"

            for timerN in range(self.timer_num):
                cb = self.timer_gen_cb(timerN, self.source, state_struct,
                    self.type_cast_macro
                )

                total_used_types.add(cb)

                code += """\
    s->%s@b=@stimer_new_ns(@aQEMU_CLOCK_VIRTUAL,@s%s,@ss);
""" % (self.timer_name(timerN), cb.name,
                )

        fn = Function(
            name = self.gen_instance_init_name(),
            body = """\
    {used}{Struct}@b*s@b=@s{UPPER}(obj);
{extra_code}\
""".format(
    Struct = state_struct.name,
    UPPER = type_cast_macro.name,
    extra_code = code,
    used = "" if s_is_used else "__attribute__((unused))@b"
            ),
            static = True,
            args = [
                Type.lookup("Object").gen_var("obj", pointer = True)
            ],
            used_types = total_used_types,
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
    .name@b@b@b@b@b@b@b@b@b@b=@sTYPE_{UPPER},
    .parent@b@b@b@b@b@b@b@b=@s{parent_tn},
    .instance_size@b=@ssizeof({Struct}),
    .instance_init@b=@s{instance_init},
    .class_init@b@b@b@b=@s{class_init}
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
        read = Type.lookup("MemoryRegionOps_read")

        used_types = set([
            read.args[1].type,
            Type.lookup("uint64_t"),
            Type.lookup("printf"),
            Type.lookup("HWADDR_PRIx")
        ])

        body = """\
    __attribute__((unused))@b{Struct}@b*s@b=@s{UPPER}(opaque);
    uint64_t@bret@b=@s0;

    switch@b({offset})@b{{
    default:
        printf(@a"%s:@bunimplemented@bread@bfrom@b0x%"HWADDR_PRIx",@bsize@b%d\
\\n",@s__FUNCTION__,@s{offset},@ssize);
        break;
    }}

    return@sret;
""".format(
    offset = read.args[1].name,
    Struct = struct_name,
    UPPER = type_cast_macro
        )

        return read.use_as_prototype(
            name = name,
            static = True,
            body = body,
            used_types = used_types
        )

    @staticmethod
    def gen_mmio_write(name, struct_name, type_cast_macro):
        write = Type.lookup("MemoryRegionOps_write")

        used_types = set([
            write.args[1].type,
            write.args[2].type,
            Type.lookup("uint64_t"),
            Type.lookup("printf"),
            Type.lookup("HWADDR_PRIx"),
            Type.lookup("PRIx64")
        ])

        body = """\
    __attribute__((unused))@b{Struct}@b*s@b=@s{UPPER}(opaque);

    switch@b({offset})@b{{
    default:
        printf(@a"%s:@bunimplemented@bwrite@bto@b0x%"HWADDR_PRIx",@bsize@b%d,@b"
               @a"value@b0x%"PRIx64"\\n",@s__FUNCTION__,@s{offset},@ssize,\
@s{value});
        break;
    }}
""".format(
    offset = write.args[1].name,
    value = write.args[2].name,
    Struct = struct_name,
    UPPER = type_cast_macro
        )

        return write.use_as_prototype(
            name = name,
            static = True,
            body = body,
            used_types = used_types
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
    __attribute_info__ = OrderedDict([
        ("directory", { "short": _("Directory"), "input": str }),
        ("block_num", { "short": _("Block driver quantity"), "input": int }),
        ("char_num", { "short": _("Character driver quantity"), "input": int }),
        ("timer_num", { "short": _("Timer quantity"), "input": int })
    ])

    def __init__(self, name, directory,
            nic_num = 0,
            timer_num = 0,
            char_num = 0,
            block_num = 0,
            **qom_kw
    ):
        super(QOMDevice, self).__init__(name, **qom_kw)

        self.directory = directory
        self.nic_num = nic_num
        self.timer_num = timer_num
        self.char_num = char_num
        self.block_num = block_num

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

    # Block driver
    def block_name(self, index):
        if self.block_num == 1:
            return "blk"
        else:
            return "blk_%u" % index

    def block_prop_name(self, index):
        pfx = self.qtn.for_macros + "_"
        if self.block_num == 1:
            return pfx + "DRIVE"
        else:
            return pfx + "DRIVE_%u" % index

    def block_declare_fields(self):
        for index in range(self.block_num):
            f = QOMStateField(
                Pointer(Type.lookup("BlockBackend")), self.block_name(index),
                save = False,
                prop = True
            )
            self.add_state_field(f)
            # override macro name assigned by `add_state_field`
            f.prop_macro_name = self.block_prop_name(index)

    # Character driver
    def char_name(self, index):
        if self.char_num == 1:
            return "chr"
        else:
            return "chr_%u" % index

    def char_can_read_name(self, index):
        return self.qtn.for_id_name + "_" + self.char_name(index) + "_can_read"

    def char_read_name(self, index):
        return self.qtn.for_id_name + "_" + self.char_name(index) + "_read"

    def char_event_name(self, index):
        return self.qtn.for_id_name + "_" + self.char_name(index) + "_event"

    def char_declare_fields(self):
        field_type = (Type.lookup("CharBackend") if get_vp()["v2.8 chardev"]
            else Pointer(Type.lookup("CharDriverState"))
        )

        for index in range(self.char_num):
            self.add_state_field(QOMStateField(
                field_type, self.char_name(index),
                save = False,
                prop = True
            ))

    def char_gen_cb(self, proto_name, handler_name, index, source,
        state_struct, type_cast_macro
    ):
        proto = Type.lookup(proto_name)
        cb = proto.use_as_prototype(handler_name,
            body = """\
    __attribute__((unused))@b%s@b*s@b=@s%s(opaque);%s
""" % (
    state_struct.name,
    self.type_cast_macro.name,
    "\n\n    return 0;" \
    if proto.ret_type not in [ None, Type.lookup("void") ] else "",
            ),
            static = True,
            used_types = set([state_struct, type_cast_macro])
        )
        source.add_type(cb)
        return cb

    def char_gen_handlers(self, index, source, state_struct, type_cast_macro):
        ret = [
            self.char_gen_cb(proto_name, handler_name, index, source,
                state_struct, type_cast_macro
            ) for proto_name, handler_name in [
                ("IOCanReadHandler", self.char_can_read_name(index)),
                ("IOReadHandler", self.char_read_name(index)),
                ("IOEventHandler", self.char_event_name(index))
            ]
        ]

        # Define handler relative order: can read, read, event
        line_origins(ret)

        return ret

    # TIMERS
    def timer_name(self, index):
        if self.timer_num == 1:
            return "timer"
        else:
            return "timer_%u" % index

    def timer_cb_name(self, index):
        return self.qtn.for_id_name + "_" + self.timer_name(index) + "_cb"

    def timer_declare_fields(self):
        for index in range(self.timer_num):
            self.add_state_field(QOMStateField(
                Pointer(Type.lookup("QEMUTimer")), self.timer_name(index),
                save = True
            ))

    def timer_gen_cb(self, index, source, state_struct, type_cast_macro):
        timer_cb = Function(self.timer_cb_name(index),
            body = """\
    __attribute__((unused))@b%s@b*s@b=@s%s(opaque);
""" % (state_struct.name, self.type_cast_macro.name
            ),
            args = [Type.lookup("void").gen_var("opaque", pointer = True)],
            static = True,
            used_types = set([state_struct, type_cast_macro])
        )
        source.add_type(timer_cb)
        return timer_cb

    # 'realize' method generation
    def gen_realize(self, dev_type_name,
        code = "",
        s_is_used = False,
        used_types = [],
        used_globals = []
    ):
        total_used_types = set([self.state_struct, self.type_cast_macro])
        total_used_types.update(used_types)

        total_used_globals = list(used_globals)

        if self.char_num > 0:
            if get_vp()["v2.8 chardev"]:
                helper_name = "qemu_chr_fe_set_handlers"
                char_name_fmt = "&s->%s"
                extra_args = ",@sNULL,@strue"
            else:
                helper_name = "qemu_chr_add_handlers"
                char_name_fmt = "s->%s"
                extra_args = ""

            total_used_types.add(Type.lookup(helper_name))
            code += "\n"
            s_is_used = True

            for chrN in range(self.char_num):
                chr_name = self.char_name(chrN)
                har_handlers = self.char_gen_handlers(chrN, self.source,
                    self.state_struct, self.type_cast_macro
                )
                code += """\
    if@b({chr_name})@b{{
        {helper_name}(@a{chr_name},@s{helpers},@ss{extra_args});
    }}
""".format(
    helper_name = helper_name,
    chr_name = char_name_fmt % chr_name,
    helpers = ",@s".join([h.name for h in har_handlers]),
    extra_args = extra_args
                )
                total_used_types.update(har_handlers)

        if self.block_num > 0:
            code += "\n"
            s_is_used = True
            # actually not, but user probably needed functions from same header
            total_used_types.add(Type.lookup("BlockDevOps"))

            for blkN in range(self.block_num):
                blk_name = self.block_name(blkN)
                code += """\
    if@b(s->%s)@b{
        /*@sTODO:@sImplement@sinteraction@swith@sblock@sdriver.@c@s*/
    }
""" % (blk_name
                )

        if self.nic_num > 0:
            code += "\n"
            s_is_used = True

            def_mac = Type.lookup("qemu_macaddr_default_if_unset")
            fmt_info = Type.lookup("qemu_format_nic_info_str")
            obj_tn = Type.lookup("object_get_typename")
            obj_cast = Type.lookup("OBJECT")
            def_cast = Type.lookup("DEVICE")
            new_nic = Type.lookup("qemu_new_nic")
            get_queue = Type.lookup("qemu_get_queue")

            total_used_types.update([def_mac, fmt_info, obj_tn, obj_cast,
                def_cast, new_nic, get_queue
            ])

            for nicN in range(self.nic_num):
                conf_name = self.nic_conf_name(nicN)
                nic_name = self.nic_name(nicN)
                info = self.gen_net_client_info(nicN)

                self.source.add_global_variable(info)
                total_used_globals.append(info)

                code += """\
    {def_mac}(&s->{conf_name}.macaddr);
    s->{nic_name}@b=@s{new_nic}(@a&{info},@s&s->{conf_name},@s{obj_tn}\
({obj_cast}(s)),@s{def_cast}(s)->id,@ss);
    {fmt_info}(@a{get_queue}(s->{nic_name}),@ss->{conf_name}.macaddr.a);
""".format(
    def_mac = def_mac.name,
    conf_name = conf_name,
    nic_name = nic_name,
    new_nic = new_nic.name,
    info = info.name,
    obj_tn = obj_tn.name,
    obj_cast = obj_cast.name,
    def_cast = def_cast.name,
    fmt_info = fmt_info.name,
    get_queue = get_queue.name
                )

        fn = Function(
            name = "%s_realize" % self.qtn.for_id_name,
            body = """\
    {unused}{Struct}@b*s@b=@s{UPPER}(dev);
{extra_code}\
""".format(
        unused = "" if s_is_used else "__attribute__((unused))@b",
        Struct = self.state_struct.name,
        UPPER = self.type_cast_macro.name,
        extra_code = code
            ),
            args = [
                Type.lookup(dev_type_name).gen_var("dev", pointer = True),
                Pointer(Type.lookup("Error")).gen_var("errp", pointer = True)
            ],
            static = True,
            used_types = total_used_types,
            used_globals = total_used_globals
        )

        return fn

    # NICs

    def nic_name(self, index):
        if self.nic_num == 1:
            return "nic"
        else:
            return "nic_%u" % index

    def nic_conf_name(self, index):
        return self.nic_name(index) + "_conf"

    def net_client_info_name(self, index):
        return self.qtn.for_id_name + "_" + self.nic_name(index) + "_info"

    def nic_helper_name(self, helper, index):
        return "%s_%s_%s" % (
            self.qtn.for_id_name, self.nic_name(index), helper
        )

    def nic_declare_field(self, index):
        self.add_state_field(
            QOMStateField(
                Pointer(Type.lookup("NICState")), self.nic_name(index),
                save = False
            )
        )
        f = QOMStateField(
            Type.lookup("NICConf"), self.nic_conf_name(index),
            save = False,
            prop = True
        )
        self.add_state_field(f)
        # NIC properties have standard names
        f.prop_macro_name = None

    def nic_declare_fields(self):
        for i in range(self.nic_num):
            self.nic_declare_field(i)

    def gen_nic_helper(self, helper, cbtn, index):
        cbt = Type.lookup(cbtn)
        return cbt.use_as_prototype(
            self.nic_helper_name(helper, index),
            body = "    return 0;\n" if cbt.ret_type.name != "void" else "",
            static = True,
            used_types = [ Type.lookup(self.struct_name) ]
        )

    def gen_net_client_info(self, index):
        helpers = []
        code = {}
        for helper_name, cbtn in [
            ("link_status_changed", "LinkStatusChanged"),
            ("can_receive", "NetCanReceive"),
            ("receive", "NetReceive"),
            ("cleanup", "NetCleanup")
        ]:
            helper = self.gen_nic_helper(helper_name, cbtn, index)
            self.source.add_type(helper)
            helpers.append(helper)
            code[helper_name] = helper

        # Define relative order of helpers: link, can recv, recv, cleanup
        line_origins(helpers)

        code["type"] = Type.lookup("NET_CLIENT_DRIVER_NIC")
        types = set([Type.lookup("NICState")] + list(code.values()))
        code["size"] = "sizeof(NICState)"

        init = Initializer(code, used_types = types)

        return Type.lookup("NetClientInfo").gen_var(
            self.net_client_info_name(index),
            initializer = init,
            static = True
        )

class QOMCPU(QOMType):
    def __init__(self, arch_name):
        self.arch_name = arch_name.lower()
        super(QOMCPU, self).__init__('CPU' + arch_name)

    def gen_state(self):
        s = super(QOMCPU, self).gen_state()
        s.append_field_t_s('CPU_COMMON', '')
        return s

    # function body is generated in TargetCPU
    # types are necessary functions + vmstate
    def gen_class_init_fn(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_class_init',
            args = [
                Type.lookup('ObjectClass').gen_var('oc',
                                                   pointer = True),
                Type.lookup('void').gen_var('data', pointer = True)
            ],
            static = True,
            used_types = used_types
        )

    def gen_reset(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_reset',
            args = [
                Type.lookup('CPUState')
            .gen_var('cs', pointer = True)],
            static = True,
            used_types = used_types
        )

    def gen_has_work(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_has_work',
            ret_type = Type.lookup('bool'),
            args = [
                Type.lookup('CPUState')
            .gen_var('cs', pointer = True)],
            static = True,
            used_types = used_types
        )

    def gen_disas_set_info(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_disas_set_info',
            args = [
                Type.lookup('CPUState')
            .gen_var('cpu', pointer = True),
                Type.lookup('disassemble_info')
            .gen_var('info', pointer = True)
            ],
            static = True,
            used_types = used_types
        )

    def gen_set_pc(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_set_pc',
            args = [
                Type.lookup('CPUState')
            .gen_var('cs', pointer = True),
                Type.lookup('vaddr').gen_var('value')
            ],
            static = True,
            used_types = used_types
        )

    def gen_class_by_name(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_class_by_name',
            ret_type = Pointer(
                Type.lookup('ObjectClass')),
            args = [
                Type.lookup('const char')
            .gen_var('cpu_model', pointer = True)
            ],
            static = True,
            used_types = used_types
        )

    def gen_do_interrupt(self):
        return Function(
            self.arch_name + '_cpu_do_interrupt',
            args = [
                Type.lookup('CPUState')
            .gen_var('cs', pointer = True)
            ]
        )

    def gen_phys_page_debug(self):
        return Function(
            self.arch_name + '_cpu_get_phys_page_debug',
            ret_type = Type.lookup('hwaddr'),
            args = [
                Type.lookup('CPUState').gen_var('cs', pointer = True),
                Type.lookup('vaddr').gen_var('addr')
            ]
        )

    def gen_dump_state(self):
        return Function(
            self.arch_name + '_cpu_dump_state',
            args = [
                Type.lookup('CPUState')
            .gen_var('cs', pointer = True),
                Type.lookup('FILE')
            .gen_var('f', pointer = True),
                Type.lookup('fprintf_function')
            .gen_var('cpu_fprintf'),
                Type.lookup('int').gen_var('flags')
            ]
        )

    def gen_translate_init(self):
        return Function(self.arch_name + '_tcg_init')

    def gen_realize_fn(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_realizefn',
            args = [
                Type.lookup('DeviceState')
            .gen_var('dev', pointer = True),
                Pointer(Type.lookup('Error'))
            .gen_var('errp', pointer = True)
            ],
            static = True,
            used_types = used_types
    )

    def gen_instance_init_fn(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_initfn',
            args = [
                Type.lookup('Object')
            .gen_var('obj', pointer = True)
            ],
            static = True,
            used_types = used_types
        )

    def gdb_read_register(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_gdb_read_register',
            ret_type = Type.lookup('int'),
            args = [
                Type.lookup('CPUState').gen_var('cs', pointer = True),
                Type.lookup('uint8_t').gen_var('mem_buf', pointer = True),
                Type.lookup('int').gen_var('n')
            ],
            static = True,
            used_types = used_types
        )

    def gdb_write_register(self, used_types = []):
        return Function(
            self.arch_name + '_cpu_gdb_write_register',
            ret_type = Type.lookup('int'),
            args = [
                Type.lookup('CPUState').gen_var('cs', pointer = True),
                Type.lookup('uint8_t').gen_var('mem_buf', pointer = True),
                Type.lookup('int').gen_var('n')
            ],
            static = True,
            used_types = used_types
        )

    def raise_exception(self, used_types = []):
        return Function(
            'raise_exception',
            ret_type = Type.lookup('void'),
            args = [
                Type.lookup(
                    'CPU' + self.arch_name.upper() + 'State'
                ).gen_var('env', pointer = True),
                Type.lookup('uint32_t').gen_var('index')
            ],
            static = True,
            used_types = used_types
        )

    def helper_debug(self, used_types = []):
        return Function(
            'helper_debug',
            ret_type = Type.lookup('void'),
            args = [
                Type.lookup(
                    'CPU' + self.arch_name.upper() + 'State'
                ).gen_var('env', pointer = True),
            ],
            used_types = used_types
        )

    def helper_illegal(self, used_types = []):
        return Function(
            'helper_illegal',
            ret_type = Type.lookup('void'),
            args = [
                Type.lookup(
                    'CPU' + self.arch_name.upper() + 'State'
                ).gen_var('env', pointer = True),
            ],
            used_types = used_types
        )
