__all__ = [
    "QOMType"
      , "QOMDevice"
      , "QOMCPU"
]

from common import (
    is_pow2,
    mlget as _,
    OrderedSet,
)
from .machine_nodes import (
    MemoryLeafNode,
)
from .model_state import (
    StateStruct,
)
from .qom_type_state_field import (
    QOMTypeStateField,
)
from .qtn import (
    QemuTypeName,
)
from .register import (
    gen_reg_cases,
    get_reg_range,
)
from source import (
    CINT,
    Function,
    Header,
    Initializer,
    line_origins,
    Macro,
    Pointer,
    Source,
    Structure,
    TopComment,
    Type,
    TypeNotRegistered,
    Variable,
)
from source.function import (
    BodyTree,
    BranchSwitch,
    Call,
    Declare,
    OpAddr,
    OpDeclareAssign,
    MCall,
    NewLine,
    Return,
    StrConcat,
    SwitchCaseDefault,
)
from .version import (
    get_vp,
)

from collections import (
    OrderedDict,
)
from math import (
    log,
)
from os.path import (
    join,
)
from six import (
    integer_types,
)


# Property declaration generation helpers

def gen_prop_declaration(field, decl_macro_name, state_struct,
    default_default = None
):
    decl_macro = Type[decl_macro_name]
    used_types = set([decl_macro])
    bool_true = Type["true"]
    bool_false = Type["false"]

    init_code = {
        "_f" : field.name,
        "_s" : state_struct,
    }

    if field.prop_macro_name is not None:
        init_code["_n"] = Type[field.prop_macro_name]
        init_code["_name"] = init_code["_n"]

    init_code["_state"] = init_code["_s"]
    init_code["_field"] = init_code["_f"]

    # _conf is name of argument of macro DEFINE_NIC_PROPERTIES that
    # corresponds to structure field name
    init_code["_conf"] = init_code["_f"]

    if default_default is not None:
        if field.property_default is None:
            val = default_default
        else:
            val = field.property_default

        if isinstance(val, str):
            try:
                val_macro = Type[val]
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
            if field.c_type_name[0] == "u":
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


class QOMType(object):

    __attribute_info__ = OrderedDict([
        ("name", { "short": _("Name"), "input": str }),
        ("directory", { "short": _("Directory"), "input": str }),
    ])

    def __init__(self, name, directory,
        extra_fields = tuple()
    ):
        self.directory = directory
        self.qtn = qtn = QemuTypeName(name)
        self.struct_name = "{}State".format(self.qtn.for_struct_name)
        self.state = StateStruct(self.struct_name,
            vmsd_state_name = qtn.for_id_name,
        )
        # an interface is either `Macro` or C string literal
        self.interfaces = OrderedSet()
        self.extra_fields = tuple(extra_fields)

    def declare_extra_fields(self):
        self.add_state_fields(self.extra_fields)

    def gen_type_cast(self):
        cast_type = get_vp("QOM type checkers type")
        if cast_type is Macro:
            cast = Macro(
                name = self.qtn.for_macros,
                args = [ "obj" ],
                text = "OBJECT_CHECK({Struct}, (obj), {TYPE_MACRO})".format(
                    TYPE_MACRO = self.qtn.type_macro,
                    Struct = self.struct_name
                )
            )
        elif cast_type is Function:
            cast = Type["OBJECT_DECLARE_SIMPLE_TYPE"].gen_type(
                name = self.qtn.for_macros,
                initializer = Initializer(
                    dict(
                        # actually Type[self.struct_name], but this conflicts
                        # with line_origins
                        InstanceType = self.struct_name,

                        MODULE_OBJ_NAME = self.qtn.for_macros,
                    ),
                    used_types = [Type[self.qtn.type_macro]],
                )
            )
        else:
            raise NotImplementedError(cast_type)

        return cast

    def co_gen_sources(self):
        self._sources = sources = []

        # Fill functions may require arbitrary file references.
        # So, we first generate all files with no content and then fill
        # them.

        try:
            fill_header = self.fill_header
        except AttributeError:
            # That type does not generate a header.
            fill_header = lambda : None
        else:
            self.header = header = self.provide_header()
            sources.append(header)

        yield
        self.source = source = self.gen_source()
        sources.append(source)

        yield
        fill_header()

        yield
        self.fill_source()

    def provide_header(self):
        header_path = join("include", "hw", self.directory,
            self.qtn.for_header_name + ".h"
        )
        try:
            return Header[header_path]
        except Exception:
            return Header(header_path)

    def gen_source(self):
        source_path = join("hw", self.directory,
            self.qtn.for_header_name + ".c"
        )
        return Source(source_path)

    def fill_source(self):
        raise NotImplementedError(
            "You must implement module content generation for type %s" % (
                self.qtn.name
            )
        )

    @property
    def sources(self):
        try:
            return self._sources
        except AttributeError:
            pass
        raise RuntimeError("First generate sources!")

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

    @property
    def fields_names(self):
        return set(f.name for f in self.iter_all_state_fields())

    def iter_all_state_fields(self):
        for f in self.state.fields:
            yield f

    def add_state_fields(self, fields):
        for field in fields:
            self.add_state_field(field)

    def add_state_field(self, field):
        field.prop_macro_name = (
            self.qtn.for_macros + "_" + field.provide_property_macro_suffix()
        )
        self.state.add_field(field)

    def add_state_field_h(self, type_name, field_name,
            num = None,
            save = True,
            prop = False,
            default = None
        ):
        f = QOMTypeStateField(type_name, field_name,
            array_size = num,
            save_in_vmsd = save,
            is_property = prop,
            property_default = default
        )
        self.add_state_field(f)

    def add_fields_for_regs(self, regs):
        for reg in regs:
            name = reg.name
            if name is None or name == "gap" or reg.virtual:
                continue

            qtn = QemuTypeName(name)

            size = reg.size

            if reg.warbits.v and reg.wmask.v:
                reg_fields = (qtn.for_id_name, qtn.for_id_name + "_war",)
            else:
                reg_fields = (qtn.for_id_name,)

            for name in reg_fields:
                if size <= 8 and is_pow2(size):
                    self.add_state_field_h("uint%u_t" % (size * 8), name)
                else:
                    # an arbitrary size, use an array
                    self.add_state_field_h("uint8_t", name, num = size)

    def gen_state(self):
        return self.state.gen_c_type()

    def gen_property_macros(self, source):
        for field in self.iter_all_state_fields():
            if not field.is_property:
                continue
            if field.prop_macro_name is None:
                continue

            t = Macro(field.prop_macro_name,
                text = field.provide_property_name(),
            )
            source.add_type(t)

    def gen_properties_initializer(self, state_struct):
        used_types = set()
        global type2prop

        code = "{"

        first = True
        for f in self.iter_all_state_fields():
            if not f.is_property:
                continue

            try:
                helper = type2prop[f.c_type_name]
            except KeyError:
                raise Exception(
                    "Property generation for type %s is not implemented" % \
                        f.c_type_name
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
        terminator_macro = Type["DEFINE_PROP_END_OF_LIST"]
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
        return Type["Property"](
            name = self.qtn.for_id_name + "_properties",
            initializer = self.gen_properties_initializer(state_struct),
            static = True,
            array_size = 0
        )

    def gen_vmstate_var(self, __):
        # avoid using TYPE macros
        # https://lists.gnu.org/archive/html/qemu-devel/2018-10/msg02175.html
        # TODO: macro expansion required
        return self.state.gen_vmstate_var(
            name_suffix = self.qtn.for_id_name,
            state_name = Type[self.qtn.type_macro].text.strip('"'),
        )

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
        type_cast_macro = Type[self.qtn.for_macros]

        total_used_types = set([state_struct, type_cast_macro])
        total_used_types.update(used_types)

        if self.timer_num > 0:
            total_used_types.update([
                Type["QEMU_CLOCK_VIRTUAL"],
                Type["timer_new_ns"]
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
            args = [ Pointer(Type["Object"])("obj") ],
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
            parent_macro = Type[parent_tn]
        except TypeNotRegistered:
            parent_macro = None
        else:
            used_types.append(parent_macro)

        if self.interfaces:
            used_types.append(Type["InterfaceInfo"])
            interfaces = []
            for i in self.interfaces:
                if not isinstance(i, Macro):
                    try:
                        i = Type[i]
                    except TypeNotRegistered:
                        pass

                if isinstance(i, Macro):
                    interfaces.append(i.name)
                    used_types.append(i)
                else:
                    interfaces.append('"%s"' % i)
        else:
            interfaces = False

        # Type info initializer
        tii = Initializer(
            code = """{{
    .name@b@b@b@b@b@b@b@b@b@b=@s{TYPE_MACRO},
    .parent@b@b@b@b@b@b@b@b=@s{parent_tn},
    .instance_size@b=@ssizeof({Struct}),
    .instance_init@b=@s{instance_init},
    .class_init@b@b@b@b=@s{class_init}{interfaces}
}}""".format(
    TYPE_MACRO = self.qtn.type_macro,
    parent_tn = ('"%s"' % parent_tn) if parent_macro is None \
                else parent_macro.name,
    Struct = state_struct.name,
    instance_init = instance_init_fn.name,
    class_init = class_init_fn.name,
    interfaces = (
        ",\n"
        "    .interfaces@b@b@b@b=@s(InterfaceInfo[])@b{\n        "
        +
        ",\n        ".join("{@b%s@s}" % i for i in interfaces)
        +
        ",\n        {@b}\n"
        "    }"
    ) if interfaces else ""
            ),
            used_types = used_types
        )
        # TypeInfo variable
        return Type["TypeInfo"](
            name = self.gen_type_info_name(),
            static = True,
            initializer = tii
        )

    def gen_register_types_fn(self, *infos):
        fn = Function(
            name = self.gen_register_types_name(),
            body = BodyTree()(*[
                Call(
                    Type["type_register_static"],
                    OpAddr(info)
                ) for info in infos
            ]),
            static = True
        )

        return fn

    @staticmethod
    def gen_mmio_read(name, struct_name, type_cast_macro, regs = None):
        func = Type["MemoryRegionOps"].read.type.type.use_as_prototype(name,
            body = BodyTree(),
            static = True
        )
        s = Pointer(Type[struct_name])("s")
        ret = Variable("ret", Type["uint64_t"])
        if regs:
            cases = gen_reg_cases(
                regs, "r", func.args[1], None, ret, func.args[2], s
            )
        else:
            cases = []

        func.body(
            Declare(OpDeclareAssign(
                s,
                MCall(type_cast_macro, func.args[0])
            )),
            Declare(OpDeclareAssign(
                ret,
                0
            )),
            NewLine(),
            BranchSwitch(func.args[1],
                cases = cases,
                separate_cases = True
            )(
                SwitchCaseDefault()(
                    Call(
                        "printf",
                        StrConcat(
                            "%s: unimplemented read from 0x%",
                            MCall("HWADDR_PRIx"),
                            ", size %d\\n",
                            delim = "@s"
                        ),
                        MCall("__func__"),
                        func.args[1],
                        func.args[2]
                    )
                )
            ),
            NewLine(),
            Return(ret)
        )

        return func

    @staticmethod
    def gen_mmio_write(name, struct_name, type_cast_macro, regs = None):
        func = Type["MemoryRegionOps"].write.type.type.use_as_prototype(name,
            body = BodyTree(),
            static = True
        )
        s = Pointer(Type[struct_name])("s")
        if regs:
            cases = gen_reg_cases(
                regs, "w", func.args[1], func.args[2], None, func.args[3], s
            )
        else:
            cases = []

        func.body(
            Declare(OpDeclareAssign(
                s,
                MCall(type_cast_macro, func.args[0])
            )),
            NewLine(),
            BranchSwitch(func.args[1],
                cases = cases,
                separate_cases = True
            )(
                SwitchCaseDefault()(
                    Call(
                        "printf",
                        StrConcat(
                            "%s: unimplemented write to 0x%",
                            MCall("HWADDR_PRIx"),
                            ", size %d, ",
                            "value 0x%",
                            MCall("PRIx64"),
                            "\\n",
                            delim = "@s"
                        ),
                        MCall("__func__"),
                        func.args[1],
                        func.args[3],
                        func.args[2]
                    )
                )
            )
        )

        return func

    @staticmethod
    def gen_mmio_size(regs):
        if regs is None:
            return CINT(0x100, 16, 3) # legacy default
        elif isinstance(regs, MemoryLeafNode):
            return regs.size
        else:
            reg_range = get_reg_range(regs)
            digits = int(log(reg_range, 16)) + 1
            return CINT(reg_range, 16, digits)


class QOMDevice(QOMType):

    __attribute_info__ = OrderedDict([
        ("block_num", { "short": _("Block driver quantity"), "input": int }),
        ("char_num", {
            "short": _("Character driver quantity"),
            "input": int
        }),
        ("timer_num", { "short": _("Timer quantity"), "input": int })
    ])

    def __init__(self, name, directory,
            nic_num = 0,
            timer_num = 0,
            char_num = 0,
            block_num = 0,
            **qom_kw
    ):
        super(QOMDevice, self).__init__(name, directory, **qom_kw)

        self.nic_num = nic_num
        self.timer_num = timer_num
        self.char_num = char_num
        self.block_num = block_num

    # Block driver
    def block_name(self, index):
        if self.block_num == 1:
            return "blk"
        else:
            return "blk_%u" % index

    def block_prop_macro_suffix(self, index):
        if self.block_num == 1:
            return "DRIVE"
        else:
            return "DRIVE_%u" % index

    def block_declare_fields(self):
        for index in range(self.block_num):
            f = QOMTypeStateField("BlockBackend*", self.block_name(index),
                save_in_vmsd = False,
                is_property = True,
                property_macro_suffix = self.block_prop_macro_suffix(index),
            )
            self.add_state_field(f)

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

    def char_backend_changed_name(self, index):
        return (
            self.qtn.for_id_name + "_" + self.char_name(index) + "_be_changed"
        )

    def char_declare_fields(self):
        field_type = ("CharBackend" if get_vp()["v2.8 chardev"]
            else "CharDriverState*"
        )

        for index in range(self.char_num):
            self.add_state_field(QOMTypeStateField(
                field_type, self.char_name(index),
                save_in_vmsd = False,
                is_property = True
            ))

    def char_gen_cb(self, proto_name, handler_name, index, source,
        state_struct, type_cast_macro, ret
    ):
        proto = Type[proto_name]
        cb = proto.use_as_prototype(handler_name,
            body = """\
    __attribute__((unused))@b%s@b*s@b=@s%s(opaque);%s
""" % (
    state_struct.name,
    self.type_cast_macro.name,
    ("\n\n    return %s;" % ret) if ret is not None else "",
            ),
            static = True,
            used_types = set([state_struct, type_cast_macro])
        )
        source.add_type(cb)
        return cb

    def char_gen_handlers(self, index, source, state_struct, type_cast_macro):
        handlers = [
            ("IOCanReadHandler", self.char_can_read_name(index), "0"),
            ("IOReadHandler", self.char_read_name(index), None),
            ("IOEventHandler", self.char_event_name(index), None)
        ]
        if get_vp("char backend hotswap handler"):
            handlers.append((
                "BackendChangeHandler",
                self.char_backend_changed_name(index),
                "-1" # hotswap is not supported by an empty device boilerplate
            ))

        ret = [
            self.char_gen_cb(proto_name, handler_name, index, source,
                state_struct, type_cast_macro, handler_ret
            ) for proto_name, handler_name, handler_ret in handlers
        ]

        # Define handler relative order: can read, read, event,
        # backend hotswap.
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
            self.add_state_field(QOMTypeStateField(
                "QEMUTimer*", self.timer_name(index),
                save_in_vmsd = True
            ))

    def timer_gen_cb(self, index, source, state_struct, type_cast_macro):
        timer_cb = Function(
            name = self.timer_cb_name(index),
            body = """\
    __attribute__((unused))@b%s@b*s@b=@s%s(opaque);
""" % (state_struct.name, self.type_cast_macro.name
            ),
            args = [ Pointer(Type["void"])("opaque") ],
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

            total_used_types.add(Type[helper_name])
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
            total_used_types.add(Type["BlockDevOps"])

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

            def_mac = Type["qemu_macaddr_default_if_unset"]
            fmt_info = Type["qemu_format_nic_info_str"]
            obj_tn = Type["object_get_typename"]
            obj_cast = Type["OBJECT"]
            def_cast = Type["DEVICE"]
            new_nic = Type["qemu_new_nic"]
            get_queue = Type["qemu_get_queue"]

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
                Pointer(Type[dev_type_name])("dev"),
                Pointer(Pointer(Type["Error"]))("errp")
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
            QOMTypeStateField(
                "NICState*", self.nic_name(index),
                save_in_vmsd = False
            )
        )
        f = QOMTypeStateField(
            "NICConf", self.nic_conf_name(index),
            save_in_vmsd = False,
            is_property = True
        )
        self.add_state_field(f)
        # NIC properties have standard names
        f.prop_macro_name = None

    def nic_declare_fields(self):
        for i in range(self.nic_num):
            self.nic_declare_field(i)

    def gen_nic_helper(self, helper, cbtn, index):
        cbt = Type[cbtn]
        return cbt.use_as_prototype(self.nic_helper_name(helper, index),
            body = "    return 0;\n" if cbt.ret_type.name != "void" else "",
            static = True,
            used_types = [ Type[self.struct_name] ]
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

        code["type"] = Type["NET_CLIENT_DRIVER_NIC"]
        types = set([Type["NICState"]] + list(code.values()))
        code["size"] = "sizeof(NICState)"

        return Type["NetClientInfo"](
            self.net_client_info_name(index),
            initializer = Initializer(code, used_types = types),
            static = True
        )


class QOMCPU(QOMType):

    def __init__(self, name, directory):
        super(QOMCPU, self).__init__(name + "-cpu", directory)
        self.cpu_name = name.lower()
        self.target_name = directory

        # redefinition of struct_name
        self.struct_name = "CPU" + self.cpu_name.upper() + "State"

        # all derived strings in one place
        self.struct_instance_name = self.qtn.for_struct_name.upper()
        self.struct_class_name = self.qtn.for_struct_name.upper() + "Class"
        self.env_get_cpu_name = self.cpu_name.lower() + "_env_get_cpu"
        self.tcg_init_name = self.cpu_name.lower() + "_tcg_init"
        self.cpu_init_name = "cpu_" + self.cpu_name.lower() + "_init"
        self.type_info_name = self.cpu_name.upper() + "_type_info"
        self.print_insn_name = "print_insn_" + self.target_name
        self.bfd_arch_name = "bfd_arch_" + self.target_name
        self.class_macro = self.qtn.for_macros + "_CLASS"
        self.get_class_macro =  self.qtn.for_macros + "_GET_CLASS"
        self.target_arch = "TARGET_" + self.target_name.upper()
        self.config_arch_dis = "CONFIG_" + self.target_name.upper() + "_DIS"

        self.state.vmsd_min_version_id = 1
        self.state.vmsd_state_name = "cpu"
        self.state.c_type_name = self.struct_name

    def gen_state(self):
        s = super(QOMCPU, self).gen_state()
        if get_vp("move tlb_flush to cpu_common_reset"):
            s.append_field(TopComment(
                "Fields up to this point are cleared by a CPU reset"
            ))
            s.append_field(Structure()("end_reset_fields"))
        if get_vp("CPU_COMMON exists"):
            cpu_common_usage = Type["CPU_COMMON"].gen_type()
            s.append_field(cpu_common_usage)
            # XXX: extra reference guarantiee that NB_MMU_MODES defined before
            # CPU_COMMON usage
            cpu_common_usage.extra_references = {Type["NB_MMU_MODES"]}
        return s

    def gen_vmstate_var(self, state_struct):
        vmstate = super(QOMCPU, self).gen_vmstate_var(state_struct)
        vmstate.static = False
        vmstate.used = True

        return vmstate

    def gen_func_name(self, func):
        return self.qtn.for_id_name + '_' + func

    def gen_raise_exception(self):
        return Function(
            name = "raise_exception",
            args = [
                Pointer(Type[self.struct_name])("env"),
                Type["uint32_t"]("index")
            ],
            static = True
        )

    def gen_helper_debug(self):
        return Function(
            name = "helper_debug",
            args = [ Pointer(Type[self.struct_name])("env") ]
        )

    def gen_helper_illegal(self):
        return Function(
            name = "helper_illegal",
            args = [ Pointer(Type[self.struct_name])("env") ]
        )
