__all__ = [
    "QOMStateField"
  , "QOMType"
      , "QOMDevice"
  , "OpaqueRegister"
      , "Register"
]

from source import (
    CINT,
    CSTR,
    line_origins,
    Source,
    Header,
    Structure,
    TypeNotRegistered,
    Initializer,
    Function,
    Macro,
    Pointer,
    Variable,
    Type
)
from os.path import (
    join
)
from six import (
    integer_types
)
from common import (
    same_attrs,
    OrderedSet,
    is_pow2,
    mlget as _
)
from collections import (
    OrderedDict
)
from .version import (
    get_vp
)
from .qtn import (
    QemuTypeName
)
from math import (
    log
)
from .machine_nodes import (
    MemoryLeafNode
)
from source.function import *


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
        if field.default is None:
            val = default_default
        else:
            val = field.default

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

        declare_int(ctn, "DEFINE_PROP_" + msfx)

        type2vmstate[ctn] = "VMSTATE_" + msfx


class OpaqueRegister(object):

    def __init__(self, size, name):
        self.size, self.name = size, name


class Register(OpaqueRegister):

    def __init__(self, size,
        # None or "gap" named registers are not backed by a state field
        name = None,
        access = "rw",
        reset = 0,
        full_name = None,
        # write mask (None corresponds 0b11...11. I.e. all bits are writable).
        wmask = None,
        # Write after read (WAR) bits. 1 marks the bit as WAR. None
        # corresponds to 0b00...00, all bits can be written without reading.
        warbits = None
    ):
        super(Register, self).__init__(size, name)
        self.access = access
        self.reset = None if reset is None else CINT(reset, 16, size * 2)
        self.full_name = full_name

        if wmask is None:
            wmask = (1 << (size * 8)) - 1
        self.wmask = CINT(wmask, 2, size * 8)

        if warbits is None:
            warbits = 0
        self.warbits = CINT(warbits, 2, size * 8)

    def __same__(self, o):
        if not isinstance(o, Register):
            return False
        return same_attrs(self, o, "name", "access", "reset", "full_name",
            "wmask", "warbits"
        )

    def __repr__(self, *args, **kwargs):
        # TODO: adapt and utilize PyGenerator.gen_args for this use case

        ret = type(self).__name__
        size = self.size

        ret += "(" + repr(size)

        name = self.name
        if name is not None:
            ret += ", name = " + repr(name)

        access = self.access
        if access != "rw":
            ret += ", access = " + repr(access)

        reset = self.reset
        if reset != CINT(0, 16, size * 2):
            ret += ", reset = " + repr(reset)

        fn = self.full_name
        if fn is not None:
            ret += ", full_name = " + repr(fn)

        wm = self.wmask
        if (wm.v != (1 << (size * 8)) - 1
        or  wm.b != 2
        or  wm.d != size * 8
        ):
            ret += ", wmask = " + repr(wm)

        warb = self.warbits
        if (warb.v != 0
        or  warb.b != 2
        or  warb.d != size * 8
        ):
            ret += ", warbits = " + repr(warb)

        ret += ")"
        return ret


def get_reg_range(regs):
    return sum(reg.size for reg in regs)

def gen_reg_cases(regs, access, offset_name, val, ret, s):
    reg_range = get_reg_range(regs)
    cases = []
    digits = int(log(reg_range, 16)) + 1

    offset = 0

    for reg in regs:
        size = reg.size

        name = reg.name
        if name is None or name == "gap":
            offset += size
            continue

        if size == 1:
            case_cond = CINT(offset, base = 16, digits = digits)
        else:
            case_cond = (
                CINT(offset, base = 16, digits = digits),
                CINT(offset + size - 1, base = 16, digits = digits)
            )
        offset += size

        case = SwitchCase(case_cond)

        comment = name
        if reg.full_name: # neither `None` nor empty string
            comment += ", " + reg.full_name

        case(Comment(comment))

        if access in reg.access:
            qtn = QemuTypeName(name)
            s_deref_war = lambda : OpSDeref(
                s,
                qtn.for_id_name + "_war"
            )
            s_deref = OpSDeref(
                s,
                qtn.for_id_name
            )

            if access == "r":
                case(
                    OpAssign(
                        ret,
                        s_deref
                    )
                )
                warb = reg.warbits
                if warb.v: # neither None nor zero
                    # There is at least one write-after-read bit in the reg.
                    wm = reg.wmask
                    if wm.v == (1 << (size * 8)) - 1:
                        # no read only bits: set WAR mask to 0xF...F
                        case(
                            OpAssign(
                                s_deref_war(),
                                OpNot(0)
                            )
                        )
                    else:
                        # writable bits, read only bits: init WAR mask with
                        # write mask
                        case(
                            OpAssign(
                                s_deref_war(),
                                wm
                            )
                        )
            elif access == "w":
                wm = reg.wmask
                warb = reg.warbits

                if warb.v and wm.v:
                    # WAR bits, writable, read only bits: use WAR mask as
                    # dynamic write mask
                    case(
                        OpAssign(
                            s_deref,
                            OpOr(
                                OpAnd(
                                    val,
                                    s_deref_war(),
                                    parenthesis = True
                                ),
                                OpAnd(
                                    s_deref,
                                    OpNot(
                                        s_deref_war()
                                    ),
                                    parenthesis = True
                                )
                            )
                        )
                    )
                elif wm.v == (1 << (size * 8)) - 1:
                    # no WAR bits, no read only bits
                    # write mask does not affect the value being assigned
                    case(
                        OpAssign(
                            s_deref,
                            val
                        )
                    )
                elif wm.v:
                    # no WAR bits, writable bits, read only bits: use static
                    # write mask
                    case(
                        OpAssign(
                            s_deref,
                            OpOr(
                                OpAnd(
                                    val,
                                    wm,
                                    parenthesis = True
                                ),
                                OpAnd(
                                    s_deref,
                                    OpNot(
                                        wm
                                    ),
                                    parenthesis = True
                                )
                            )
                        )
                    )
        else:
            case(
                Call(
                    "fprintf",
                    MCall("stderr"),
                    StrConcat(
                        CSTR(
"%%s: %s 0x%%0%d" % ("Reading from" if access == "r" else "Writing to", digits)
                        ),
                        MCall("HWADDR_PRIx"),
                        CSTR("\\n"),
                        delim = "@s"
                    ),
                    MCall("__func__"),
                    offset_name
                )
            )

        cases.append(case)

    return cases


class QOMType(object):
    __attribute_info__ = OrderedDict([
        ("name", { "short": _("Name"), "input": str }),
        ("directory", { "short": _("Directory"), "input": str }),
    ])

    def __init__(self, name, directory):
        self.directory = directory
        self.qtn = QemuTypeName(name)
        self.struct_name = "{}State".format(self.qtn.for_struct_name)
        self.state_fields = []
        # an interface is either `Macro` or C string literal
        self.interfaces = OrderedSet()

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
        return set(f.name for f in self.state_fields)

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
        t = Type[type_name]
        f = QOMStateField(t, field_name,
            num = num,
            save = save,
            prop = prop,
            default = default
        )
        self.add_state_field(f)

    def add_fields_for_regs(self, regs):
        for reg in regs:
            name = reg.name
            if name is None or name == "gap":
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
        s = Structure(self.struct_name)
        for f in self.state_fields:
            s.append_field(f.type(f.name, array_size = f.num))
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
                helper = type2prop[f.type.c_name]
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

    def gen_vmstate_initializer(self, name, state_struct,
        min_version_id = None
    ):
        code = """{{
    .name@b=@s{name},
    .version_id@b=@s1,{min_version_id}
    .fields@b=@s(VMStateField[])@b{{
""".format(
    name = name,
    min_version_id = ("\n    .minimum_version_id@b=@s%d," % min_version_id
        if min_version_id else ""
    )
        )

        used_macros = set()
        global type2vmstate

        for f in self.state_fields:
            if not f.save:
                continue

            # code of macro initializer is dict
            fdict = {
                "_f": f.name,
                "_s": state_struct.name,
                # Macros may use different argument names
                "_field": f.name,
                "_state": state_struct.name
            }

            try:
                vms_macro_name = type2vmstate[f.type.c_name]
            except KeyError:
                raise Exception(
                    "VMState generation for type %s is not implemented" % \
                        f.type.name
                )

            if f.num is not None:
                vms_macro_name += "_ARRAY"
                fdict["_n"] = str(f.num)

            vms_macro = Type[vms_macro_name]
            used_macros.add(vms_macro)

            code += " " * 8 + vms_macro.gen_usage_string(Initializer(fdict))

            code += ",\n"

        # Generate VM state list terminator macro.
        code += " " * 8 + Type["VMSTATE_END_OF_LIST"].gen_usage_string()

        code += "\n    }\n}"

        init = Initializer(
            code = code,
            used_types = used_macros.union([
                Type["VMStateField"],
                state_struct
            ])
        )
        return init

    def gen_vmstate_var(self, state_struct):
        # avoid using TYPE macros
        # https://lists.gnu.org/archive/html/qemu-devel/2018-10/msg02175.html
        # TODO: macro expansion required
        v_name = Type[self.qtn.type_macro].text
        return Type["VMStateDescription"](
            name = "vmstate_%s" % self.qtn.for_id_name,
            static = True,
            const = True,
            initializer = self.gen_vmstate_initializer(v_name, state_struct)
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
            cases = gen_reg_cases(regs, "r", func.args[1], None, ret, s)
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
                regs, "w", func.args[1], func.args[2], None, s
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
                            StrConcat(
                                ", size %d, ",
                                "value 0x%",
                                delim = "@s"
                            ),
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

    def block_prop_name(self, index):
        pfx = self.qtn.for_macros + "_"
        if self.block_num == 1:
            return pfx + "DRIVE"
        else:
            return pfx + "DRIVE_%u" % index

    def block_declare_fields(self):
        for index in range(self.block_num):
            f = QOMStateField(
                Pointer(Type["BlockBackend"]), self.block_name(index),
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

    def char_backend_changed_name(self, index):
        return (
            self.qtn.for_id_name + "_" + self.char_name(index) + "_be_changed"
        )

    def char_declare_fields(self):
        field_type = (Type["CharBackend"] if get_vp()["v2.8 chardev"]
            else Pointer(Type["CharDriverState"])
        )

        for index in range(self.char_num):
            self.add_state_field(QOMStateField(
                field_type, self.char_name(index),
                save = False,
                prop = True
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
            self.add_state_field(QOMStateField(
                Pointer(Type["QEMUTimer"]), self.timer_name(index),
                save = True
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
            QOMStateField(
                Pointer(Type["NICState"]), self.nic_name(index),
                save = False
            )
        )
        f = QOMStateField(
            Type["NICConf"], self.nic_conf_name(index),
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
