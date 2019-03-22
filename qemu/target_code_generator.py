__all__ = [
    "TargetCodeGenerator"
  , "CPURegister"
  , "gen_reg_names_range"
  , "BYTE_SIZE"
  , "SUPPORTED_READ_SIZES"
]


from re import (
    finditer
)
from copy import (
    copy
)
from source import (
    BodyTree,
    BranchElse,
    BranchIf,
    BranchSwitch,
    Break,
    CINT,
    CSTR,
    Call,
    Comment,
    Declare,
    Function,
    Goto,
    Header,
    Ifdef,
    Label,
    LoopDoWhile,
    LoopFor,
    MCall,
    MacroBranch,
    NewLine,
    Node,
    NodeVisitor,
    OpAdd,
    OpAddr,
    OpAnd,
    OpAssign,
    OpCast,
    OpCombAssign,
    OpDeclareAssign,
    OpDeref,
    OpEq,
    OpGE,
    OpGreater,
    OpIndex,
    OpLShift,
    OpLess,
    OpLogAnd,
    OpLogNot,
    OpLogOr,
    OpNEq,
    OpOr,
    OpPreInc,
    OpRShift,
    OpRem,
    OpSDeref,
    OpSizeOf,
    OpSub,
    Pointer,
    Return,
    SwitchCase,
    SwitchCaseDefault,
    Type,
    Variable
)
from .version import (
    get_vp
)
from collections import (
    defaultdict
)
from six import (
    integer_types
)
from common import (
    ee
)
from itertools import (
    count
)


DEBUG_DECODER = ee("DEBUG_DECODER")


# sizes in bits
BYTE_SIZE = 8
OPERAND_MAX_SIZE = 64
SUPPORTED_READ_SIZES = [8, 16, 32, 64]


class CPURegister(object):
    "Class is used to describe CPUState registers and register groups."

    def __init__(self, name, bitsize, *reg_names):
        """
    :param reg_names:
        if the list is not empty then the CPURegister describes a group of
    registers
        """
        self.name = name
        self.bitsize = bitsize
        self.reg_names = reg_names
        if reg_names:
            self._len = len(reg_names)
        else:
            self._len = None

    @property
    def size(self):
        if self.bitsize <= 32:
            return 4
        elif self.bitsize <= 64:
            return 8
        else:
            raise ValueError("Wrong register size: " + self.name)

    @property
    def len(self):
        return self._len


def gen_reg_names_range(base_name, suffix = "", start = 0, end = 1):
    assert(type(start) is type(end))
    if isinstance(start, integer_types):
        func = str
    elif isinstance(start, str) and len(start) == 1 and len(end) == 1:
        func = chr
        start = ord(start[0])
        end = ord(end[0])
    else:
        raise ValueError("Register names range generating error: only integer"
            " or one char ranges are allowed"
        )
    return [base_name + func(i) + suffix for i in range(start, end)]


class IterationHandler(object):

    def __init__(self, target_bigendian, read_size, gen_node, instr_node,
        gen_field_read_cb, epilogue_cb, result, default_switch_case
    ):
        self.target_bigendian = target_bigendian
        self.read_size = read_size
        self.gen_field_read_cb = gen_field_read_cb
        self.epilogue_cb = epilogue_cb
        self.result = result
        self.default_switch_case = default_switch_case

        # divide vars by purpose
        self.opcode_vars = set()
        self.operands_vars = set()
        self.vars = set()

        self.handle_iteration(gen_node, instr_node)

        # auto naming vars by purpose
        for var in self.opcode_vars:
            var.name = "opc" + var.name
        for var in self.operands_vars - self.opcode_vars:
            var.name = "val" + var.name
        for var in self.vars - self.operands_vars - self.opcode_vars:
            var.name = "res" + var.name

    def read_fields(self, node, reads_desc):
        vals = []

        for offset, length in reads_desc:
            val = Type["uint64_t"]("%d_%d" % (offset // BYTE_SIZE, length))
            val_desc = (val, offset, length)
            vals.append(val_desc)
            self.gen_field_read_cb(node, *val_desc)

        return vals

    def calc_shift_val(self, var_offset, var_length, offset, length):
        local_offset = offset - var_offset

        # We must consider the endianess of CPU if the variable is larger
        # than the read size.
        if self.target_bigendian:
            shift_val = var_length - length - local_offset
        else:
            swap_size = self.read_size
            shift_val = (swap_size + local_offset -
                2 * (local_offset % swap_size) - length
            )

        return shift_val

    def get_operand_part(self, oper, vars_desc):
        for var, var_off, var_len in vars_desc:
            if (    var_off <= oper.offset
                and oper.offset + oper.length <= var_off + var_len
            ):
                break

        shift_val = self.calc_shift_val(var_off, var_len, oper.offset,
            oper.length
        )

        self.operands_vars.add(var)
        res = OpAnd(
            OpRShift(var, shift_val) if shift_val else var,
            CINT((1 << oper.length) - 1, base = 16)
        )

        return res

    def get_operands(self, node, instruction, vars_desc):
        declarations = []
        operands = []

        for name, parts in instruction.operand_parts():
            shift = 0
            rval = None
            need_parenthesis = len(parts) > 1

            for oper in parts:
                oper_part = self.get_operand_part(oper, vars_desc)

                # Prevent warning [-Wparentheses]
                # "suggest parentheses around arithmetic in operand of `|`"
                # when the operand is merged from several parts.
                oper_part.parenthesis = need_parenthesis

                if shift:
                    oper_part = OpLShift(oper_part, shift)
                rval = OpOr(rval, oper_part) if rval else oper_part
                shift += oper.length

            if shift > OPERAND_MAX_SIZE:
                raise RuntimeError('The operand "%s" in the instruction "%s"'
                    " longer than %d bits. Please reduce the length manually"
                    " by breaking it into several operands." % (
                        name, instruction.mnemonic, OPERAND_MAX_SIZE
                    )
                )

            res = Type["uint64_t"](name)
            operands.append(res)
            declarations.append(Declare(OpDeclareAssign(res, rval)))

        node(*declarations)
        return operands

    def handle_iteration(self, gen_node, instr_node, vars_desc = []):
        opc = instr_node.opcode
        ins = instr_node.instruction
        reads_desc = instr_node.reads_desc

        if ins is None:
            new_vars = self.read_fields(gen_node, reads_desc)
            if new_vars is not None:
                vars_desc = vars_desc + new_vars
                self.vars.update(v[0] for v in new_vars)

            for var, var_off, var_len in reversed(vars_desc):
                if (    var_off <= opc[0]
                    and opc[0] + opc[1] <= var_off + var_len
                ):
                    break

            shift_val = self.calc_shift_val(var_off, var_len, opc[0], opc[1])

            cases = []
            default_sc = None
            for key, node in instr_node.subtree.items():
                if key == "default":
                    sc = default_sc = SwitchCaseDefault()
                else:
                    sc = SwitchCase(
                        CINT(
                            int(key, base = 2) << shift_val,
                            base = 16
                        )
                    )
                    cases.append(sc)

                self.handle_iteration(sc, node, vars_desc = vars_desc)

            if default_sc is not None:
                cases.append(default_sc)
            else:
                # If subtree hasn't `default` key it means subtree hasn't
                # instr_node with `default` opc and we must exit cpu loop in
                # `default` branch.
                cases.append(self.default_switch_case)

            opc_mask = int('1' * opc[1], base = 2) << shift_val

            self.opcode_vars.add(var)
            gen_node(
                BranchSwitch(
                    OpAnd(var, CINT(opc_mask, base = 16)),
                    cases = cases
                )
            )
        else:
            text = ins.comment
            gen_node(Comment(text))

            new_vars = self.read_fields(gen_node, reads_desc)
            if new_vars is not None:
                vars_desc = vars_desc + new_vars
                self.vars.update(v[0] for v in new_vars)

            operands = self.get_operands(gen_node, ins, vars_desc)

            self.epilogue_cb(gen_node, instr_node, operands, text)

            total_read = (vars_desc[-1][1] + vars_desc[-1][2]) // BYTE_SIZE
            gen_node(OpAssign(self.result, total_read))


class VariablesLinker(NodeVisitor):
    """ Visitor tries to replace all CSTR strings to corresponding variables.
Limitations:
    Able to handle only variables with unique names.
    """

    def __init__(self, root, variables):
        super(VariablesLinker, self).__init__(root)

        self.vars_dict = { v.name: v for v in variables }

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Variable):
            self.vars_dict[cur.name] = cur
        elif isinstance(cur, (CSTR, str)):
            try:
                self.replace(self.vars_dict[str(cur)])
            except:
                pass


class TargetCodeGenerator(object):
    """ This class contains glue utilities to get rid of direct body tree
filling in arch creation code
    """

    def __init__(self, cpu):
        self.cpu = cpu

    def gen_cpu_class_by_name(self, function):
        oc = Pointer(Type["ObjectClass"])("oc")
        cpu_model = function.args[0]
        null = MCall("NULL")

        function.body = root = BodyTree()

        if get_vp("cpu_model null check"):
            root(
                Declare(oc),
                NewLine(),
                BranchIf(OpEq(cpu_model, null))(Return(null)),
                OpAssign(oc, Call("object_class_by_name", cpu_model))
            )
        else:
            root(
                Declare(
                    OpDeclareAssign(
                        oc,
                        Call("object_class_by_name", cpu_model)
                    )
                )
            )

        root(
            BranchIf(
                OpLogAnd(
                    OpNEq(oc, null),
                    OpLogOr(
                        OpEq(
                            Call(
                                "object_class_dynamic_cast",
                                oc,
                                MCall(self.cpu.qtn.type_macro)
                            ),
                            null
                        ),
                        Call("object_class_is_abstract", oc)
                    )
                )
            )(Return(null)),
            Return(oc)
        )

    def gen_cpu_class_init(self, function, num_core_regs, vmstate):
        root = BodyTree()
        function.body = root

        oc = function.args[0]
        dc = Pointer(Type["DeviceClass"])("dc")
        cc = Pointer(Type["CPUClass"])("cc")
        mcc = Pointer(Type[self.cpu.struct_class_name()])("mcc")

        fn = self.cpu.func_name

        root(
            Declare(
                OpDeclareAssign(
                    dc,
                    MCall("DEVICE_CLASS", oc)
                )
            ),
            Declare(
                OpDeclareAssign(
                    cc,
                    MCall("CPU_CLASS", oc)
                )
            ),
            Declare(
                OpDeclareAssign(
                    mcc,
                    MCall(self.cpu.class_macro(), oc)
                )
            ),
            NewLine()
        )

        if get_vp("device_class_set_parent_realize exists"):
            root(
                Call(
                    "device_class_set_parent_realize",
                    dc,
                    Type[fn("realizefn")],
                    OpAddr(OpSDeref(mcc, "parent_realize")),
                )
            )
        else:
            root(
                OpAssign(
                    OpSDeref(mcc, "parent_realize"),
                    OpSDeref(dc, "realize")
                ),
                OpAssign(
                    OpSDeref(dc, "realize"),
                    Type[fn("realizefn")]
                )
            )

        root(
            OpAssign(
                OpSDeref(mcc, "parent_reset"),
                OpSDeref(cc, "reset")
            )
        )
        root(*[
            OpAssign(
                OpSDeref(cc, name),
                Type[fn(name)]
            ) for name in ["reset", "has_work", "do_interrupt", "set_pc",
                "dump_state", "disas_set_info", "class_by_name"
            ]
        ])
        root(
            OpAssign(
                OpSDeref(cc, "vmsd"),
                OpAddr(vmstate)
            ),
            OpAssign(
                OpSDeref(cc, "gdb_num_core_regs"),
                num_core_regs
            )
        )
        root(*[
            OpAssign(
                OpSDeref(cc, name),
                Type[fn(name)]
            ) for name in ["gdb_read_register", "gdb_write_register",
                "get_phys_page_debug"
            ]
        ])

        if get_vp("Generic call to tcg_initialize"):
            root(
                OpAssign(
                    OpSDeref(cc, "tcg_initialize"),
                    Type[self.cpu.tcg_init_name()]
                )
            )

        if get_vp("CPUClass has tlb_fill field"):
            root(
                OpAssign(
                    OpSDeref(cc, "tlb_fill"),
                    Type[self.cpu.func_name("tlb_fill")]
                )
            )

    def gen_cpu_disas_set_info(self, function):
        function.body = BodyTree()(
            OpAssign(
                OpSDeref(function.args[1], "mach"),
                getattr(Type["bfd_architecture"], self.cpu.bfd_arch_name())
            ),
            OpAssign(
                OpSDeref(function.args[1], "print_insn"),
                Type[self.cpu.print_insn_name()]
            )
        )

    def gen_cpu_env_get_cpu(self, function):
        function.body = BodyTree()(
            Return(
                MCall(
                    "container_of",
                    function.args[0],
                    Type[self.cpu.struct_name],
                    Node("env")
                )
            )
        )

    def gen_cpu_gdb_rw_register(self, function, comment):
        qom = self.cpu
        cpu = Pointer(Type[qom.struct_name])("cpu")
        cc = Pointer(Type["CPUClass"])("cc")
        env = Pointer(Type[qom.struct_state_name()])("env")

        ret_0 = Return(0)

        function.body = BodyTree()(
            Comment(comment),
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(qom.qtn.for_macros, function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    cc,
                    MCall("CPU_GET_CLASS", function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    env,
                    OpAddr(OpSDeref(cpu, "env"))
                )
            ),
            NewLine(),
            BranchIf(
                OpGreater(
                    function.args[2],
                    OpSDeref(cc, "gdb_num_core_regs")
                )
            )(ret_0),
            ret_0
        )

    def gen_cpu_get_tb_cpu_state(self, function):
        function.body = BodyTree()(
            OpAssign(
                OpDeref(function.args[1]),
                OpSDeref(function.args[0], self.cpu.pc_register)
            ),
            OpAssign(OpDeref(function.args[2]), 0),
            OpAssign(OpDeref(function.args[3]), 0)
        )

    def gen_cpu_has_work(self, function):
        function.body = BodyTree()(
            Return(
                OpAnd(
                    OpSDeref(function.args[0], "interrupt_request"),
                    MCall("CPU_INTERRUPT_HARD")
                )
            )
        )

    def gen_cpu_init(self, function):
        qtn = self.cpu.qtn
        function.body = BodyTree()(
            Return(
                MCall(
                    qtn.for_macros,
                    Call("cpu_generic_init", MCall(qtn.type_macro),
                        function.args[0]
                    )
                )
            )
        )

    def gen_cpu_initfn(self, function):
        root = BodyTree()
        function.body = root

        qtn = self.cpu.qtn
        cpu = Pointer(Type[self.cpu.struct_name])("cpu")
        cs = Pointer(Type["CPUState"])("cs")

        if get_vp("cpu_set_cpustate_pointers exists"):
            root(
                Declare(
                    OpDeclareAssign(
                        cpu,
                        MCall(qtn.for_macros, function.args[0])
                    )
                ),
                NewLine(),
                Call(
                    "cpu_set_cpustate_pointers",
                    cpu
                )
            )
        elif get_vp("Generic call to tcg_initialize"):
            root(
                Declare(
                    OpDeclareAssign(
                        cs,
                        MCall("CPU", function.args[0])
                    )
                ),
                Declare(
                    OpDeclareAssign(
                        cpu,
                        MCall(qtn.for_macros, function.args[0])
                    )
                ),
                NewLine(),
                OpAssign(
                    OpSDeref(cs, "env_ptr"),
                    OpAddr(OpSDeref(cpu, "env"))
                )
            )
        else:
            inited = Type["int"]("inited", static = True)

            root(
                Declare(
                    OpDeclareAssign(
                        cs,
                        MCall("CPU", function.args[0])
                    )
                ),
                Declare(
                    OpDeclareAssign(
                        cpu,
                        MCall(qtn.for_macros, function.args[0])
                    )
                ),
                Declare(inited),
                NewLine(),
                OpAssign(
                    OpSDeref(cs, "env_ptr"),
                    OpAddr(OpSDeref(cpu, "env"))
                ),
                BranchIf(
                    OpLogAnd(
                        Call("tcg_enabled"),
                        OpLogNot(inited)
                    )
                )(
                    OpAssign(inited, 1),
                    Call(self.cpu.tcg_init_name())
                )
            )

    def gen_cpu_mmu_index(self, function):
        function.body = BodyTree()(Return(0))

    def gen_cpu_realizefn(self, function):
        cs = Pointer(Type["CPUState"])("cs")
        cc = Pointer(Type[self.cpu.struct_class_name()])("cc")
        err = Pointer(Type["Error"])("local_err")
        null = MCall("NULL")

        function.body = BodyTree()(
            Declare(
                OpDeclareAssign(
                    cs,
                    MCall("CPU", function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    cc,
                    MCall(self.cpu.get_class_macro(), function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    err,
                    null
                )
            ),
            NewLine(),
            Call("cpu_exec_realizefn", cs, OpAddr(err)),
            BranchIf(OpNEq(err, null))(
                Call("error_propagate", function.args[1], err),
                Return()
            ),
            Call("qemu_init_vcpu", cs),
            Call("cpu_reset", cs),
            Call(
                OpSDeref(cc, "parent_realize"),
                function.args[0],
                function.args[1]
            )
        )

    def gen_cpu_reset(self, function):
        qom = self.cpu
        cpu = Pointer(Type[qom.struct_name])("cpu")
        cc = Pointer(Type[qom.struct_class_name()])("cc")
        env = Pointer(Type[qom.struct_state_name()])("env")

        function.body = root = BodyTree()

        root(
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(qom.qtn.for_macros, function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    cc,
                    MCall(qom.get_class_macro(), cpu)
                )
            ),
            Declare(
                OpDeclareAssign(
                    env,
                    OpAddr(OpSDeref(cpu, "env"))
                )
            ),
            NewLine(),
            Call(
                OpSDeref(cc, "parent_reset"),
                function.args[0]
            )
        )

        if get_vp("move tlb_flush to cpu_common_reset"):
            root(
                Call(
                    "memset",
                    env,
                    0,
                    MCall(
                        "offsetof",
                        Type[qom.struct_state_name()],
                        Node("end_reset_fields")
                    )
                ),
                OpAssign(
                    OpSDeref(env, qom.pc_register),
                    0
                )
            )
        else:
            root(
                Call(
                    "memset",
                    env,
                    0,
                    OpSizeOf(
                        Type[qom.struct_state_name()]
                    )
                ),
                OpAssign(
                    OpSDeref(env, qom.pc_register),
                    0
                ),
                Call(
                    "tlb_flush",
                    function.args[0],
                    1
                )
            )

    def gen_cpu_set_pc(self, function):
        qtn = self.cpu.qtn
        cpu = Pointer(Type[self.cpu.struct_name])("cpu")

        function.body = BodyTree()(
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(qtn.for_macros, function.args[0])
                )
            ),
            NewLine(),
            OpAssign(
                OpSDeref(OpSDeref(cpu, "env"), self.cpu.pc_register),
                function.args[1]
            )
        )

    def gen_disas_bfd_getb64(self, function):
        ull = "unsigned long long"
        v = Type[ull].gen_var("v")
        addr = function.args[0]
        function.body = BodyTree()(
            Declare(v),
            NewLine(),
            OpAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 0), 56))),
            OpCombAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 1), 48)), "|"),
            OpCombAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 2), 40)), "|"),
            OpCombAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 3), 32)), "|"),
            OpCombAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 4), 24)), "|"),
            OpCombAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 5), 16)), "|"),
            OpCombAssign(v, OpCast(ull, OpLShift(OpIndex(addr, 6), 8)), "|"),
            OpCombAssign(v, OpCast(ull, OpIndex(addr, 7)), "|"),
            Return(OpCast("bfd_vma", v))
        )

    def gen_disas_print_insn(self, function):
        root = BodyTree()
        function.body = root

        status = Type["int"]("status")
        buffer_ = Type["bfd_byte"]("buffer", array_size = 6)
        length = Type["int"]("length")
        stream = Pointer(Type["void"])("stream")
        fpr = Type["fprintf_function"]("fpr")

        root(
            Declare(status),
            Declare(buffer_),
            Declare(
                OpDeclareAssign(
                    length,
                    2
                )
            ),
            Declare(
                OpDeclareAssign(
                    stream,
                    OpSDeref(function.args[1], "stream")
                )
            ),
            Declare(
                OpDeclareAssign(
                    fpr,
                    OpSDeref(function.args[1], "fprintf_func")
                )
            ),
            NewLine()
        )

        fail_lbl = Label("fail")

        default_switch_case_nodes = [
            Call("fprintf", MCall("stderr"), "Unknown instruction\\n"),
            Call("abort")
        ]
        default_switch_case = SwitchCaseDefault(add_break = False)(
            *default_switch_case_nodes
        )

        def gen_disas_opcode_read(node, val, offset, length):
            offset //= BYTE_SIZE
            byte_length = length // BYTE_SIZE
            addr = function.args[0]
            info = function.args[1]

            node(
                OpAssign(
                    status,
                    Call(
                        OpSDeref(info, "read_memory_func"),
                        OpAdd(addr, offset) if offset else addr,
                        buffer_,
                        byte_length,
                        info
                    )
                ),
                BranchIf(status)(Goto(fail_lbl))
            )

            if byte_length == 1:
                bfd_get = OpIndex(buffer_, 0)
            else:
                bfd_get = Call(
                    "bfd_get%s%d" % (
                        'b' if self.cpu.target_bigendian else 'l',
                        length
                    ),
                    buffer_
                )
                # shift result due to implementation of bfd_getb16
                if self.cpu.target_bigendian and length == 16:
                    bfd_get = OpRShift(bfd_get, 16)

            node(Declare(OpDeclareAssign(val, bfd_get)))

        def print_ins_epilogue(gen_node, instr_node, operands, _):
            operands_dict = { o.name: o for o in operands }

            format_line = ''
            call_args = []
            name_to_format = self.cpu.name_to_format
            for m in finditer("<(.+?)>|([^<>]+)",
                instr_node.instruction.disas_format
            ):
                try:
                    gr = m.group(1)
                    v = name_to_format[gr]
                    variables = []
                    for i in gr.split(','):
                        name = i.strip().split('$')[0]
                        variables.append(operands_dict.get(name, CINT(name)))

                    if v[0] is None:
                        if format_line:
                            gen_node(
                                Call(fpr, stream, format_line, *call_args)
                            )
                            format_line = ''
                            call_args = []
                        gen_node(Call(v[1], fpr, stream, *variables))
                        continue
                    else:
                        format_line += v[0]

                    if v[1] is None:
                        for var in variables:
                            if isinstance(var, Variable):
                                call_args.append(OpCast("unsigned", var))
                            else:
                                call_args.append(var)
                    else:
                        call_args.append(Call(v[1], *variables))
                except KeyError:
                    format_line += m.group(0)

            if format_line:
                gen_node(Call(fpr, stream, format_line, *call_args))

        instruction_tree_root = self.cpu.instruction_tree_root
        if instruction_tree_root:
            IterationHandler(self.cpu.target_bigendian, self.cpu.read_size,
                root, instruction_tree_root, gen_disas_opcode_read,
                print_ins_epilogue, length, default_switch_case
            )
        else:
            root(*default_switch_case_nodes)

        root(
            Return(length),
            fail_lbl,
            Call(
                OpSDeref(function.args[1], "memory_error_func"),
                status,
                function.args[0],
                function.args[1]
            ),
            Return(-1)
        )

    def gen_helper_cpu_tlb_fill(self, function):
        prot = Type["int"]("prot")

        function.body = BodyTree()(
            Declare(
                OpDeclareAssign(
                    prot,
                    OpOr(
                        MCall("PAGE_READ"),
                        OpOr(
                            MCall("PAGE_WRITE"),
                            MCall("PAGE_EXEC")
                        )
                    )
                )
            ),
            OpCombAssign(function.args[1], MCall("TARGET_PAGE_MASK"), "&"),
            Call(
                "tlb_set_page",
                function.args[0],
                function.args[1],
                function.args[1],
                prot,
                function.args[-3],
                MCall("TARGET_PAGE_SIZE")
            ),
            Return(Type["true"])
        )

    def gen_helper_debug(self, function):
        function.body = BodyTree()(
            Call(
                "raise_exception",
                function.args[0],
                MCall("EXCP_DEBUG")
            )
        )

    def gen_helper_disas_write(self, function):
        function.body = BodyTree()(Return(0))

    def gen_helper_get_phys_page_debug(self, function):
        function.body = BodyTree()(Return(function.args[1]))

    def gen_helper_handle_mmu_fault(self, function):
        prot = Type["int"]("prot")

        function.body = BodyTree()(
            Declare(
                OpDeclareAssign(
                    prot,
                    OpOr(
                        MCall("PAGE_READ"),
                        OpOr(
                            MCall("PAGE_WRITE"),
                            MCall("PAGE_EXEC")
                        )
                    )
                )
            ),
            OpCombAssign(function.args[1], MCall("TARGET_PAGE_MASK"), "&"),
            Call(
                "tlb_set_page",
                function.args[0],
                function.args[1],
                function.args[1],
                prot,
                function.args[-1],
                MCall("TARGET_PAGE_SIZE")
            ),
            Return(0)
        )

    def gen_helper_illegal(self, function):
        function.body = BodyTree()(
            Call(
                "raise_exception",
                function.args[0],
                Type["EXCP_ILLEGAL"]
            )
        )

    def gen_helper_raise_exception(self, function):
        cs = Pointer(Type["CPUState"])("cs")

        function.body = BodyTree()(
            Declare(
                OpDeclareAssign(
                    cs,
                    (
                        Call("env_cpu", function.args[0]) if get_vp(
                            "env_cpu exists"
                        ) else
                        MCall(
                            "CPU",
                            Call(self.cpu.env_get_cpu_name(), function.args[0])
                        )
                    )
                )
            ),
            NewLine(),
            OpAssign(
                OpSDeref(cs, "exception_index"),
                function.args[1]
            ),
            Call("cpu_loop_exit", cs)
        )

    def gen_helper_tlb_fill(self, function):
        function.body = root = BodyTree()

        if get_vp("CPUClass has tlb_fill field"):
            root(
                Call(
                    self.cpu.func_name("tlb_fill"),
                    function.args[0],
                    function.args[1],
                    function.args[2],
                    function.args[3],
                    function.args[4],
                    Type["false"],
                    function.args[5]
                )
            )
        else:
            ret = Type["int"]("ret")

            root(
                Declare(
                    OpDeclareAssign(
                        ret,
                        Call(
                            self.cpu.func_name("handle_mmu_fault"),
                            *function.args[:-1]
                        )
                    )
                ),
                BranchIf(MCall("unlikely", ret))(
                    Call(
                        "cpu_loop_exit_restore",
                        function.args[0],
                        function.args[-1]
                    )
                )
            )

    def gen_translate_cpu_dump_state(self, function, reg_vars):
        root = BodyTree()
        function.body = root

        qom_cpu = self.cpu
        cpu = Pointer(Type[qom_cpu.struct_name])("cpu")
        env = Pointer(Type[qom_cpu.struct_state_name()])("env")

        out_file = function.args[1]
        if get_vp("dump_state has cpu_fprintf argument"):
            fprintf_func = function.args[2]
        else:
            fprintf_func = Type["qemu_fprintf"]
        i = Type["int"]("i")

        root(
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(qom_cpu.qtn.for_macros, function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    env,
                    OpAddr(OpSDeref(cpu, "env"))
                )
            ),
            Declare(i),
            NewLine()
        )

        for r, _, names_array in reg_vars:
            if r.len:
                root(
                    LoopFor(OpAssign(i, 0), OpLess(i, r.len), OpPreInc(i))(
                        Call(
                            fprintf_func,
                            out_file,
                            "%s=0x%08x",
                            OpIndex(names_array, i),
                            OpIndex(OpSDeref(env, r.name), i)
                        ),
                        BranchIf(OpEq(OpRem(i, 4), 3))(
                            Call(fprintf_func, out_file, "\\n"),
                            BranchElse()(Call(fprintf_func, out_file, ' '))
                        )
                    )
                )
            else:
                root(
                    Call(
                        fprintf_func,
                        out_file,
                        r.name + "=0x%08x\\n",
                        OpSDeref(env, r.name)
                    )
                )

    def gen_translate_decode_opc(self, function, cpu_env):
        root = BodyTree()
        function.body = root

        result = Type["int"]("result")
        root(Declare(OpDeclareAssign(result, 0)))

        ctx = function.args[1]
        ctx_pc = OpSDeref(ctx, "pc")
        set_pc_ref = {Type["set_pc"]}

        default_switch_case_nodes = [
            Call("set_pc", ctx_pc),
            Call("gen_helper_illegal", cpu_env),
            OpAssign(
                OpSDeref(ctx, "bstate"),
                Type["BS_EXCP"]
            )
        ]
        default_switch_case = SwitchCaseDefault()(*default_switch_case_nodes)

        h = self.cpu.gen_files["translate.inc.c"]

        h_globals = list(h.global_variables.values())

        def gen_field_read(node, val, offset, length):
            offset //= BYTE_SIZE
            length //= BYTE_SIZE
            env = OpAddr(OpSDeref(function.args[0], "env"))

            suffixes = {
                1: 'ub',
                2: 'uw',
                4: 'l',
                8: 'q'
            }

            cpu_ld = Call(
                "cpu_ld%s_code" % suffixes[length],
                env,
                OpAdd(ctx_pc, offset) if offset else ctx_pc
            )

            node(Declare(OpDeclareAssign(val, cpu_ld)))

        def decode_opc_epilogue(gen_node, instr_node, operands, text):
            instr_args = [ Pointer(Type["DisasContext"])("ctx") ]
            existing_names = defaultdict(lambda : count(0))
            for o in operands:
                v = copy(o)
                parts = o.name.split('_')
                if len(parts) > 1:
                    # Operand names with underscores are shortened.
                    # Only the first and second part of the name are used.
                    # The first letter is taken from the first part.
                    # If the first part of the name ends with a number, then it
                    # is also taken.
                    i = len(parts[0]) - 1
                    while parts[0][i].isdigit():
                        i = i - 1
                    name = parts[0][0] + parts[0][i + 1:] + parts[1]
                else:
                    name = o.name
                # Getting a unique name among all operands by adding a sequence
                # number.
                while True:
                    num = next(existing_names[name])
                    if num > 0:
                        print('Warning: auto-counter on the arg "%s" of the'
                            ' "%s" instruction' % (o.name, text)
                        )
                        name = name + str(num)
                    else:
                        break
                v.name = name
                instr_args.append(v)

            body = BodyTree()(
                Comment(text),
                *instr_node.instruction.semantics()
            )
            VariablesLinker(body, instr_args + h_globals).visit()
            func = Function(
                name = instr_node.instruction.name,
                body = body,
                args = instr_args,
                static = True,
                inline = True
            )
            func.extra_references = set_pc_ref
            h.add_type(func)

            gen_node(Call(func, ctx, *operands))

            if DEBUG_DECODER:
                gen_node(
                    Call(
                        "fprintf",
                        MCall("stderr"),
                        '\"%s[%s](%s)\\n\"' % (
                            func.name,
                            instr_node.instruction.comment,
                            ",@s".join(["%lx"] * len(operands))
                        ),
                        *operands
                    )
                )

            if (    instr_node.instruction.branch
                and not DEBUG_DECODER
            ):
                gen_node(
                    OpAssign(
                        OpSDeref(ctx, "bstate"),
                        Type["BS_BRANCH"]
                    )
                )

        instruction_tree_root = self.cpu.instruction_tree_root
        if instruction_tree_root:
            IterationHandler(self.cpu.target_bigendian, self.cpu.read_size,
                root, instruction_tree_root, gen_field_read,
                decode_opc_epilogue, result, default_switch_case
            )
        else:
            root(*default_switch_case_nodes)

        root(Return(result))

    def gen_translate_gen_intermediate_code(self, function, cpu_env):
        function.body = root = BodyTree()
        qom_cpu = self.cpu

        if get_vp("gen_intermediate_code arg1 is generic"):
            env = Pointer(Type[qom_cpu.struct_state_name()])("env")
            root(
                Declare(
                    OpDeclareAssign(
                        env,
                        OpSDeref(function.args[0], "env_ptr")
                    )
                )
            )
        else:
            env = function.args[0]

        cpu = Pointer(Type[qom_cpu.struct_name])("cpu")
        ctx = Type["DisasContext"]("ctx")
        ctx_pc = OpSDeref(ctx, "pc")
        ctx_tb = OpSDeref(ctx, "tb")
        set_pc = Call("set_pc", ctx_pc)
        gen_helper_debug = Call("gen_helper_debug", cpu_env)
        ctx_bstate = OpSDeref(ctx, "bstate")
        tb = function.args[1]

        root(
            Declare(
                OpDeclareAssign(
                    cpu,
                    Call(
                        (
                            "env_archcpu" if get_vp("env_archcpu exists") else
                            self.cpu.env_get_cpu_name()
                        ),
                        env
                    )
                )
            ),
            Declare(ctx)
        )

        if get_vp("gen_intermediate_code arg1 is generic"):
            cs = function.args[0]
        else:
            cs = Pointer(Type["CPUState"])("cs")
            root(
                Declare(
                    OpDeclareAssign(
                        cs,
                        MCall("CPU", cpu)
                    )
                )
            )

        cs_bp = OpAddr(OpSDeref(cs, "breakpoints"))
        bp = Pointer(Type["CPUBreakpoint"])("bp")
        pc_start = Type["target_ulong"]("pc_start")
        done_gen = Label("done_generating")
        log_target_disas_args = [ cs, pc_start, OpSub(ctx_pc, pc_start) ]
        if get_vp("log_target_disas has FLAGS argument"):
            log_target_disas_args.append(0)
        num_insns = Type["int"]("num_insns")
        insns = [ num_insns ]
        if not get_vp("gen_intermediate_code has max_insns argument"):
            max_insns = Type["int"]("max_insns")
            insns.append(max_insns)

        root(
            Declare(bp),
            Declare(pc_start),
            Declare(*insns),
            NewLine(),
            OpAssign(pc_start, OpSDeref(tb, "pc")),
            OpAssign(ctx_pc, pc_start),
            OpAssign(ctx_tb, tb),
            OpAssign(
                ctx_bstate,
                Type["BS_NONE"]
            ),
            OpAssign(num_insns, 0)
        )

        if not get_vp("gen_intermediate_code has max_insns argument"):
            root(
                OpAssign(
                    max_insns,
                    OpAnd(
                        (
                            Call("tb_cflags", tb) if get_vp("tb_cflags exists")
                            else
                            OpSDeref(tb, "cflags")
                        ),
                        MCall("CF_COUNT_MASK")
                    )
                ),
                BranchIf(OpEq(max_insns, 0))(
                    OpAssign(max_insns, MCall("CF_COUNT_MASK"))
                ),
                BranchIf(OpGreater(max_insns, MCall("TCG_MAX_INSNS")))(
                    OpAssign(max_insns, MCall("TCG_MAX_INSNS"))
                )
            )

        tcg_gen_exit_tb_args = [ 0 ]
        if get_vp("pass tb and index to tcg_gen_exit_tb separately"):
            tcg_gen_exit_tb_args.insert(0, MCall("NULL"))

        root(
            NewLine(),
            Call("gen_tb_start", tb),
            LoopDoWhile(
                OpLogAnd(
                    OpLogNot(Call("tcg_op_buf_full")),
                    OpEq(ctx_bstate, Type["BS_NONE"])
                )
            )(
                Call("tcg_gen_insn_start", ctx_pc),
                OpCombAssign(num_insns, 1, "+"),
                BranchIf(
                    MCall(
                        "unlikely",
                        OpLogNot(MCall("QTAILQ_EMPTY", cs_bp))
                    )
                )(
                    MacroBranch(
                        MCall("QTAILQ_FOREACH", bp, cs_bp, Node("entry"))
                    )(BranchIf(OpEq(ctx_pc, OpSDeref(bp, "pc")))(
                        set_pc,
                        gen_helper_debug,
                        OpAssign(
                            ctx_bstate,
                            Type["BS_EXCP"]
                        ),
                        Comment("The address covered by the breakpoint must be"
                            " included in [tb->pc, tb->pc + tb->size) in order"
                            " to for it to be properly cleared -- thus we"
                            " increment the PC here so that the logic setting"
                            " tb->size below does the right thing."
                        ),
                        OpCombAssign(
                            ctx_pc,
# See https://lists.gnu.org/archive/html/qemu-devel/2015-10/msg03668.html
                            int(self.cpu.min_instr_size / 8),
                            "+"
                        ),
                        Goto(done_gen)
                    ))
                ),
                OpCombAssign(
                    ctx_pc,
                    Call("decode_opc", cpu, OpAddr(ctx)),
                    "+"
                ),
                BranchIf(
                    OpGE(
                        num_insns,
                        (
                            function.args[-1] if get_vp(
                                "gen_intermediate_code has max_insns argument"
                            ) else
                            max_insns
                        )
                    )
                )(Break()),
                BranchIf(
                    OpEq(
                        OpAnd(
                            ctx_pc,
                            OpSub(
                                MCall("TARGET_PAGE_SIZE"),
                                1,
                                parenthesis = True
                            ),
                        ),
                        0
                    )
                )(Break()),
                BranchIf(OpSDeref(cs, "singlestep_enabled"))(Break())
            ),
            BranchIf(OpSDeref(cs, "singlestep_enabled"))(
                BranchIf(
                    OpLogOr(
                        OpEq(ctx_bstate, Type["BS_NONE"]),
                        OpEq(ctx_bstate, Type["BS_STOP"])
                    )
                )(set_pc),
                gen_helper_debug,
                BranchElse()(
                    BranchSwitch(OpSDeref(ctx, "bstate"),
                        cases = [
                            SwitchCase(Type["BS_STOP"], add_break = False),
                            SwitchCase(Type["BS_NONE"])(set_pc),
                            SwitchCase(Type["BS_EXCP"], add_break = False),
                            SwitchCase(Type["BS_BRANCH"], add_break = False)
                        ]
                    ),
                    Call(
                        "tcg_gen_exit_tb",
                        *tcg_gen_exit_tb_args
                    )
                )
            ),
            done_gen,
            Call("gen_tb_end", tb, num_insns),
            OpAssign(
                OpSDeref(tb, "size"),
                OpSub(ctx_pc, pc_start)
            ),
            OpAssign(
                OpSDeref(tb, "icount"),
                num_insns
            ),
            # Disas
            Ifdef("DEBUG_DISAS")(
                BranchIf(
                    OpLogAnd(
                        Call("qemu_loglevel_mask", MCall("CPU_LOG_TB_IN_ASM")),
                        Call("qemu_log_in_addr_range", pc_start)
                    )
                )(
                    Call("qemu_log_lock"),
                    Call(
                        "qemu_log",
                        "IN: %s\\n",
                        Call("lookup_symbol", pc_start)
                    ),
                    Call("log_target_disas", *log_target_disas_args),
                    Call("qemu_log", "\\n"),
                    Call("qemu_log_unlock")
                )
            )
        )

    def gen_translate_inc_set_pc(self, function, pc):
        function.body = BodyTree()(OpAssign(pc, function.args[0]))

    def gen_translate_restore_state_to_opc(self, function):
        function.body = BodyTree()(
            OpAssign(
                OpSDeref(function.args[0], self.cpu.pc_register),
                OpIndex(function.args[2], 0)
            )
        )

    def gen_translate_tcg_init(self, function, reg_vars, cpu_env):
        function.body = root = BodyTree()
        i = Type["int"]("i")

        if get_vp("Generic call to tcg_initialize"):
            root(
                Declare(i),
                NewLine()
            )
        else:
            done_init = Type["int"]("done_init", static = True)
            root(
                Declare(done_init),
                Declare(i),
                NewLine(),
                BranchIf(done_init)(
                    Return()
                )
            )

        if get_vp("Init cpu_env in arch"):
            root(
                OpAssign(
                    cpu_env,
                    Call("tcg_global_reg_new_ptr", MCall("TCG_AREG0"), "env")
                ),
                OpAssign(
                    OpSDeref(
                        Header["tcg.h"].global_variables["tcg_ctx"],
                        "tcg_env"
                    ),
                    cpu_env
                )
            )

        cpu_arch_state = Type[self.cpu.struct_state_name()]
        for r, var, names_array in reg_vars:
            if r.len:
                parent_node = LoopFor(
                    OpAssign(i, 0), OpLess(i, r.len), OpPreInc(i)
                )
                root(parent_node)
                v = OpIndex(var, i)
                state_field = OpIndex(Node(r.name), i)
                string_name = OpIndex(names_array, i)
            else:
                parent_node = root
                v = var
                state_field = Node(r.name)
                string_name = r.name

            parent_node(
                OpAssign(
                    v,
                    Call(
                        "tcg_global_mem_new_i" + str(r.size * BYTE_SIZE),
                        cpu_env,
                        MCall("offsetof", cpu_arch_state, state_field),
                        string_name
                    )
                )
            )

        if not get_vp("Generic call to tcg_initialize"):
            root(OpAssign(done_init, 1))
