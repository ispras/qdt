__all__ = [
    "TargetCodeGenerator"
  , "CPURegisterGroup"
]

from source.function import *

from .instruction import (
    BYTE_SIZE,
    Operand
)
from math import (
    ceil,
    log
)
from re import (
    findall,
    finditer
)
from copy import (
    copy
)
from source import (
    Type,
    Function,
    CINT,
    Header,
    Variable
)
from .version import (
    get_vp
)
from struct import (
    pack,
    unpack
)
from collections import (
    OrderedDict
)
import os


class CPURegisterGroup(object):
    """ this exists for more convenient handling of different CPUState register
arrays - one group is one array
    """

    def __init__(self, name, regs):
        self.name = name
        self.size = None
        self.regs = []
        self.add_registers(regs)

    def add_register(self, reg):
        self.regs.append(reg)
        if self.size is None:
            self.size = reg.size
        else:
            if self.size != reg.size:
                raise ValueError(
                    "Register sizes in CPURegisterGroup must be identical"
                )

    def add_registers(self, regs):
        for r in regs:
            self.add_register(r)

    def __len__(self):
        return len(self.regs)


class IterationHandler(object):

    def __init__(self, tcg, gen_node, instr_node, field_read, field_read_args,
        epilogue, result, default_switch_case,
        verbose = True
    ):
        self.tcg = tcg
        self.field_read = field_read
        self.field_read_args = field_read_args
        self.epilogue = epilogue
        self.result = result
        self.default_switch_case = default_switch_case
        self.verbose = verbose

        self.handle_opc_iter(gen_node, instr_node, 0)

    def handle_opc_iter(self, gen_node, instr_node, total_read,
        last_read = 0,
        cur_vars = [],
        is_default = True
    ):
        opc = instr_node.opcode
        opc_dict = OrderedDict(sorted(instr_node.opc_dict.items()))

        ins = instr_node.instruction
        if ins is None:
            new_var, cur_read = self.field_read(
                gen_node,
                opc[0],
                opc[1],
                *self.field_read_args,
                already_read = total_read,
                is_opcode = True
            )
            # new_var is None means cur_read = 0 and nothing was read
            # still should use variable read previously
            if new_var is None:
                read_var = cur_vars[-1]
                new_last_read = last_read
                new_vars = cur_vars
            else:
                read_var = new_var
                new_last_read = cur_read
                new_vars = cur_vars + [new_var]

            total_read += cur_read
            shift_val = total_read * BYTE_SIZE - (opc[0] + opc[1])
            shift_str = shift_val * '0'
            swap_size = new_last_read * BYTE_SIZE
            cases = []
            default_sc = None
            for key, node in opc_dict.items():
                if key.isdigit():
                    key += shift_str
                    sc = SwitchCase(
                        CINT(
                            self.tcg.fit_endian(int(key, base = 2), swap_size),
                            base = 16
                        )
                    )
                    cases.append(sc)
                    is_default = False
                else:
                    default_sc = SwitchCaseDefault()
                    sc = default_sc
                    is_default = True
                self.handle_opc_iter(
                    sc,
                    node,
                    total_read,
                    new_last_read,
                    new_vars,
                    is_default
                )

            if default_sc is not None:
                cases.append(default_sc)
            else:
                # if opc_dict hasn't key 'default'
                # it means opc_dict hasn't instr_node with 'default' opc
                # and we must exit cpu loop in 'default' branch
                cases.append(self.default_switch_case)

            opc_mask = self.tcg.fit_endian(
                int('1' * opc[1], base = 2) << shift_val,
                swap_size
            )

            gen_node(
                BranchSwitch(
                    OpAnd(read_var, CINT(opc_mask, base = 16)),
                    cases = cases
                )
            )
        else:
            text = ins.comment or ins.mnem
            gen_node(Comment(text))

            if self.verbose and is_default:
                print(
                    'Warning: "%s" arguments intersect with the opcode' %
                    text
                )

            new_var, new_read = self.field_read(
                gen_node,
                total_read * BYTE_SIZE,
                len(ins) - total_read * BYTE_SIZE,
                *self.field_read_args,
                already_read = total_read
            )
            total_read += new_read
            if new_var is None:
                new_vars = cur_vars
            else:
                new_vars = cur_vars + [new_var]

            opers = self.tcg.gen_extract_operands(
                gen_node,
                ins,
                new_vars
            )

            self.epilogue(gen_node, instr_node, opers, text)

            gen_node(
                OpAssign(self.result, total_read)
            )


class TargetCodeGenerator(object):
    """ This class contains glue utilities to get rid of direct body tree
filling in arch creation code
    """

    def __init__(self, cpu):
        self.cpu = cpu

    def fit_endian(self, i, len):
        if not self.cpu.need_fit_endian:
            return i
        if len <= 8:
            return i
        elif len <= 16:
            c = "H"
        elif len <= 32:
            c = "L"
        else:
            c = "Q"
        res = unpack("<" + c, pack(">" + c, i))[0]
        return res

    def gen_extract_field(self, res, var, offset, length, cur_read, prev_read):
        cur_offset = offset - prev_read * BYTE_SIZE
        if self.cpu.need_fit_endian:
            be_byte_num = cur_offset // BYTE_SIZE
            le_byte_num = (cur_read - 1) - be_byte_num
            shift_val = (cur_read * BYTE_SIZE -
                (le_byte_num * BYTE_SIZE + cur_offset % BYTE_SIZE + length)
            )
        else:
            shift_val = cur_read * BYTE_SIZE - (cur_offset + length)

        if shift_val < 0:
            # TODO: replace >> with <<?
            raise ValueError()

        return OpAssign(
            res,
            OpAnd(
                OpRShift(var, shift_val),
                # TODO: is binary mask more convenient?
                CINT((1 << length) - 1, base = 16)
            )
        )

    def gen_extract_operands(self, node, instruction, read_vars):
        offset = 0
        decls = []

        i = iter(read_vars)
        v = next(i)

        for f in instruction.fields:
            if isinstance(f, Operand):
                # looking for corresponding variable to extract the value
                while True:
                    var_off, var_len = [
                        int(val) for val in findall("\d+", v.name)
                    ]
                    if (var_off * BYTE_SIZE <= offset < offset + f.length <= 
                        var_off * BYTE_SIZE + var_len
                    ):
                        break
                    else:
                        try:
                            v = next(i)
                        except StopIteration:
                            raise Exception(
"Didn't find proper var for field at offset %d in %s" % (
    offset,
    instruction.mnem
)
                            )
                else:
                    raise Exception(
"Didn't find proper var for field at offset %d in %s" % (
    offset,
    instruction.mnem
)
                    )

                res = Type["uint64_t"].gen_var(
                    "%s:%d:%d" % (f.val, f.end, f.start)
                )

                decl = self.gen_extract_field(
                    Declare(res),
                    v,
                    offset,
                    f.length,
                    var_len // BYTE_SIZE,
                    var_off
                )
                decls.append(decl)

            offset += f.length

        new_decls = []
        seen = []

        # every decl has the following form:
        #          OpAssign
        #      /              \
        #   Declare         OpAnd
        #     |           /       \
        #    res     OpRshift     Const
        #           /        \
        #          var     Const
        # in the following code we want to
        # merge operand parts together, i.e.
        # e.g. src-imm_23_16 and src-imm_15_0
        # should turn into one src-imm variable (and then to src_imm)
        for d1 in decls:
            if d1 in seen:
                continue
            seen.append(d1)
            d1ch = d1.children[0].children[0]
            same_vars = []
            same_vars.append((d1ch, d1.children[1]))
            name1 = d1ch.name

            for d2 in decls:
                if d2 not in seen:
                    d2ch = d2.children[0].children[0]
                    name2 = d2ch.name
                    i1 = name1.find(':')
                    i2 = name2.find(':')
                    if name1[:i1] == name2[:i2]:
                        same_vars.append((d2ch, d2.children[1]))
                        seen.append(d2)

            if len(same_vars) > 1:
                rval = None
                for t in same_vars:
                    v = t[0]
                    _, low = [
                        int(val) for val in findall("(?::)(\d+)", v.name)
                    ]
                    if rval is None:
                        rval = OpLShift(t[1], low)
                    else:
                        rval = OpOr(rval, OpLShift(t[1], low))
                v = same_vars[0][0].name

                res = Type["uint64_t"].gen_var(v[:v.find(':') + 1])

                if res.name[-1] == ':':
                    res.name = res.name[:-1]
                res.name = res.name.replace(':', '_')
                new_decls.append(
                    OpAssign(
                        Declare(res),
                        rval
                    )
                )
            else:
                ind = d1ch.name.find(':')
                d1ch.name = d1ch.name[:ind].replace(':', '_')
                new_decls.append(d1)

        node(*new_decls)
        return [d.children[0].children[0] for d in new_decls]

    def gen_val_byte_num(self,
        offset,
        length,
        already_read = 0,
        is_opcode = False
    ):
        byte_num = (offset + length + BYTE_SIZE - 1) // BYTE_SIZE
        assert(byte_num >= 0)
        byte_num -= already_read
        if byte_num < 1:
            return None, 0

        # need to read multiple of the read_size val
        byte_num = int(ceil(byte_num * 1.0 / self.cpu.read_size) *
            self.cpu.read_size
        )
        assert(byte_num <= 8)

        val = Type["uint64_t"].gen_var("%s%d_%d" % (
            "opc" if is_opcode else "val",
            already_read,
            byte_num * BYTE_SIZE
        ))

        return val, byte_num

    def gen_field_read(self,
        node,
        offset,
        length,
        env,
        pc,
        already_read = 0,
        is_opcode = False
    ):
        val, byte_num = self.gen_val_byte_num(offset, length,
            already_read = already_read,
            is_opcode = is_opcode
        )
        if byte_num == 0:
            return None, 0

        suffixes = {
            1: 'ub',
            2: 'uw',
            4: 'l',
            8: 'q'
        }

        expr = None
        prev_read = 0

        for k in range(0, int(log(byte_num, 2)) + 1):
            if byte_num & (1 << k):
                read = Call(
                    "cpu_ld" + suffixes[1 << k] + "_code",
                    env,
                    OpAdd(pc, already_read + prev_read)
                )

                if expr is None:
                    expr = read
                else:
                    expr = OpOr(expr, OpLShift(read, prev_read << k))

                prev_read += 1
        assert(expr is not None)

        node(
            OpAssign(Declare(val), expr)
        )

        return val, byte_num

    def gen_decode_opc(self, function, cpu_pc, cpu_env):
        root = BodyTree()
        function.body = root

        result = Type["int"].gen_var("result")
        root(
            OpAssign(
                Declare(result),
                0
            )
        )

        ctx = function.args[1]
        ctx_pc = OpSDeref(ctx, "pc")
        br_enum = Type["br_enum"]
        set_pc_func = {Type["set_pc"]}
        debug_decoder = (os.getenv("DEBUG_DECODER", "False") == "True")

        default_switch_case = SwitchCaseDefault(add_break = False)(
            Call("set_pc", ctx_pc),
            Call("gen_helper_illegal", cpu_env),
            OpAssign(
                OpSDeref(ctx, "bstate"),
                br_enum.get_field("BS_EXCP")
            ),
            Break()
        )

        h = self.cpu.gen_files["translate.inc.c"]

        def decode_opc_epilogue(gen_node, instr_node, opers, text):
            instr_args = [Type["DisasContext"].gen_var("ctx", pointer = True)]
            names_dict = {}
            for o in opers:
                v = copy(o)
                parts = o.name.split('_')
                if len(parts) > 1:
                    try:
                        names_dict[parts[0] + parts[1]] += 1
                        parts[0] += str(names_dict[parts[0] + parts[1]])
                        print("Warning: auto-counter on the args of " + text +
                            " instruction"
                        )
                    except KeyError:
                        names_dict.update({parts[0] + parts[1]: 1})

                    v.name = (parts[0][0] +
                        (parts[0][-1] if parts[0][-1].isdigit() else '') +
                        parts[1]
                    )
                else:
                    v.name = parts[0]
                instr_args.append(v)

            func = Function(
                name = instr_node.instruction.name,
                body = BodyTree()(Comment(text)),
                args = instr_args,
                static = True,
                inline = True
            )
            func.extra_references = set_pc_func
            h.add_type(func)

            gen_node(
                Call(func, ctx, *opers)
            )

            if debug_decoder:
                gen_node(
                    Call(
                        "fprintf",
                        MCall("stderr"),
                        '\"%s[%s](%s)\\n\"' % (
                            func.name,
                            instr_node.instruction.comment,
                            ("%lx, " * len(opers))[:-2]
                        ),
                        *opers
                    )
                )

            if (    instr_node.instruction.branch
                and not debug_decoder
            ):
                gen_node(
                    OpAssign(
                        OpSDeref(ctx, "bstate"),
                        br_enum.get_field("BS_BRANCH")
                    )
                )

        IterationHandler(
            self,
            root,
            self.cpu.instr_tree_root,
            self.gen_field_read,
            [OpAddr(OpSDeref(function.args[0], "env")), ctx_pc],
            decode_opc_epilogue,
            result,
            default_switch_case
        )
        root(
            Return(result)
        )

    def gen_disas_opcode_read(self,
        node,
        offset,
        length,
        addr,
        status,
        buf,
        info,
        fail_label,
        already_read = 0,
        is_opcode = False
    ):
        val, byte_num = self.gen_val_byte_num(offset, length,
            already_read = already_read,
            is_opcode = is_opcode
        )
        if byte_num == 0:
            return None, 0

        node(
            OpAssign(
                status,
                Call(
                    OpSDeref(info, "read_memory_func"),
                    OpAdd(addr, already_read),
                    buf,
                    byte_num,
                    info
                )
            ),
            BranchIf(status)(
                Goto(fail_label)
            )
        )

        if byte_num == 1:
            bfd_get = OpIndex(buf, 0)
        else:
            bfd_get = Call(
                "bfd_get%s%d" % (
                    'b' if self.cpu.arch_bigendian else 'l',
                    byte_num * BYTE_SIZE
                ),
                buf
            )

        node(
            OpAssign(Declare(val), bfd_get)
        )

        return val, byte_num

    def gen_print_ins(self, function):
        root = BodyTree()
        function.body = root

        status = Type["int"].gen_var("status")
        buffer = Type["bfd_byte"].gen_var("buffer", array_size = 6)
        length = Type["int"].gen_var("length")
        stream = Type["void"].gen_var("stream", pointer = True)
        fpr = Type["fprintf_function"].gen_var("fpr")

        root(
            Declare(status),
            Declare(buffer),
            OpAssign(
                Declare(length),
                2
            ),
            OpAssign(
                Declare(stream),
                OpSDeref(
                    function.args[1],
                    "stream"
                )
            ),
            OpAssign(
                Declare(fpr),
                OpSDeref(
                    function.args[1],
                    "fprintf_func"
                )
            )
        )

        fail_lbl = Label("fail")

        default_switch_case = SwitchCaseDefault(add_break = False)(
            Call(
                "fprintf",
                MCall("stderr"),
                "Unknown instruction\\n"
            ),
            Call("abort")
        )

        def print_ins_epilogue(gen_node, instr_node, opers, _):
            opers_dict = {o.name : o for o in opers}

            format_line = ''
            opers_call = []
            name_to_format = self.cpu.name_to_format
            for m in finditer("<(.+?)>|([^<>]+)",
                instr_node.instruction.format
            ):
                try:
                    gr = m.group(1)
                    v = name_to_format[gr]
                    vars = []
                    for i in gr.split(','):
                        name = i.strip().split('$')[0]
                        vars.append(opers_dict.get(name, CINT(name)))

                    if v[0] is None:
                        if format_line:
                            gen_node(
                                Call(
                                    fpr,
                                    stream,
                                    format_line,
                                    *opers_call
                                )
                            )
                            format_line = ''
                            opers_call = []
                        gen_node(
                            Call(
                                v[1],
                                fpr,
                                stream,
                                *vars
                            )
                        )
                        continue
                    else:
                        format_line += v[0]

                    if v[1] is None:
                        for var in vars:
                            if isinstance(var, Variable):
                                opers_call.append(OpCast("unsigned", var))
                            else:
                                opers_call.append(var)
                    else:
                        opers_call.append(Call(v[1], *vars))
                except KeyError:
                    format_line += m.group(0)

            if format_line:
                gen_node(
                    Call(
                        fpr,
                        stream,
                        format_line,
                        *opers_call
                    )
                )

        IterationHandler(
            self,
            root,
            self.cpu.instr_tree_root,
            self.gen_disas_opcode_read,
            [function.args[0], status, buffer, function.args[1], fail_lbl],
            print_ins_epilogue,
            length,
            default_switch_case,
            True
        )
        root(
            Return(length),
            fail_lbl,
            Call(
                OpSDeref(function.args[1], "memory_error_func"),
                status, function.args[0], function.args[1]
            ),
            Return(-1)
        )

    def gen_gen_intermediate_code(self, function, cpu_pc, cpu_env):
        root = BodyTree()
        function.body = root
        qom_cpu = self.cpu.qom_cpu

        if get_vp("gen_intermediate_code arg1 is generic"):
            env = Type[qom_cpu.struct_state_name()].gen_var("env",
                pointer = True
            )
            root(
                OpAssign(
                    Declare(env),
                    OpSDeref(function.args[0], "env_ptr")
                )
            )
        else:
            env = function.args[0]

        cpu = Type[qom_cpu.struct_name].gen_var("cpu", pointer = True)

        root(
            OpAssign(
                Declare(cpu),
                Call(
                    self.cpu.qom_cpu.env_get_cpu_name(),
                    env
                )
            )
        )

        br_enum = Type["br_enum"]
        ctx = Type["DisasContext"].gen_var("ctx")
        ctx_pc = OpSDeref(ctx, "pc")
        ctx_tb = OpSDeref(ctx, "tb")
        set_pc = Call("set_pc", ctx_pc)
        gen_helper_debug = Call(
            "gen_helper_debug",
            cpu_env
        )
        ctx_bstate = OpSDeref(ctx, "bstate")

        tb = function.args[1]

        if not get_vp("gen_intermediate_code arg1 is generic"):
            cs = Type["CPUState"].gen_var("cs", pointer = True)
            root(
                OpAssign(
                    Declare(cs),
                    MCall("CPU", cpu)
                )
            )
        else:
            cs = function.args[0]

        cs_bp = OpAddr(OpSDeref(cs, "breakpoints"))
        bp = Type["CPUBreakpoint"].gen_var("bp", pointer = True)
        pc_start = Type["int"].gen_var("pc_start")
        num_insns = Type["int"].gen_var("num_insns")
        max_insns = Type["int"].gen_var("max_insns")
        done_gen = Label("done_generating")
        target_disas_args = [cs, pc_start, OpSub(ctx_pc, pc_start)]
        if get_vp("target_disas has FLAGS argument"):
            target_disas_args.append(0)

        root(
            Declare(bp),
            Declare(pc_start),
            Declare(num_insns, max_insns),
            OpAssign(num_insns, 0),
            OpAssign(
                max_insns,
                OpAnd(
                    OpSDeref(tb, "cflags"),
                    MCall("CF_COUNT_MASK")
                )
            ),
            Declare(ctx),
            OpAssign(
                ctx_bstate,
                br_enum.get_field("BS_NONE")
            ),
            BranchIf(OpEq(max_insns, 0))(
                OpAssign(max_insns, MCall("CF_COUNT_MASK"))
            ),
            BranchIf(OpGreater(max_insns, MCall("TCG_MAX_INSNS")))(
                OpAssign(max_insns, MCall("TCG_MAX_INSNS"))
            ),
            OpAssign(pc_start, OpSDeref(tb, "pc")),
            OpAssign(ctx_pc, pc_start),
            OpAssign(ctx_tb, tb),
            Call("gen_tb_start", tb),
            LoopDoWhile(
                OpLogAnd(
                    OpLogNot(Call("tcg_op_buf_full")),
                    OpEq(ctx_bstate, br_enum.get_field("BS_NONE"))
                )
            )(
                BranchIf(
                    MCall(
                        "unlikely",
                        OpLogNot(MCall(
                            "QTAILQ_EMPTY",
                            cs_bp
                        ))
                    )
                )(
                    MacroBranch(
                        MCall(
                            "QTAILQ_FOREACH",
                            bp,
                            cs_bp,
                            Node("entry")
                        )
                    )(
                        BranchIf(OpEq(ctx_pc, OpSDeref(bp, "pc")))(
                            set_pc,
                            gen_helper_debug,
                            OpAssign(
                                ctx_bstate,
                                br_enum.get_field("BS_EXCP")
                            ),
                            Goto(done_gen)
                        )
                    )
                ),
                Call("tcg_gen_insn_start", ctx_pc),
                OpCombAssign(
                    ctx_pc,
                    Call("decode_opc", cpu, OpAddr(ctx)),
                    "+"
                ),
                OpCombAssign(num_insns, 1, "+"),
                BranchIf(OpGE(num_insns, max_insns))(
                    Break()
                ),
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
                )(
                    Break()
                ),
                BranchIf(OpSDeref(cs, "singlestep_enabled"))(
                    Break()
                )
            ),
            BranchIf(OpSDeref(cs, "singlestep_enabled"))(
                BranchIf(
                    OpLogOr(
                        OpEq(ctx_bstate, br_enum.get_field("BS_NONE")),
                        OpEq(ctx_bstate, br_enum.get_field("BS_STOP")),
                    )
                )(
                    set_pc
                ),
                gen_helper_debug,
                BranchElse()(
                    BranchSwitch(
                        OpSDeref(ctx, "bstate"),
                        cases = [
                            SwitchCase(br_enum.get_field("BS_STOP"),
                                add_break = False
                            ),
                            SwitchCase(br_enum.get_field("BS_NONE"))(
                                set_pc
                            ),
                            SwitchCase(br_enum.get_field("BS_EXCP"),
                                add_break = False
                            ),
                            SwitchCase(br_enum.get_field("BS_BRANCH"),
                                add_break = False
                            )
                        ],
                    ),
                    Call("tcg_gen_exit_tb", 0)
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
                        Call(
                            "qemu_loglevel_mask",
                            MCall("CPU_LOG_TB_IN_ASM")
                        ),
                        Call(
                            "qemu_log_in_addr_range",
                            pc_start
                        )
                    )
                )(
                    Call("qemu_log_lock"),
                    Call(
                        "qemu_log",
                        "IN: %s\\n",
                        Call("lookup_symbol", pc_start)
                    ),
                    Call(
                        "log_target_disas",
                        *target_disas_args
                    ),
                    Call(
                        "qemu_log",
                        "\\n"
                    ),
                    Call("qemu_log_unlock")
                )
            )
        )

    def gen_cpu_class_initfn(self, function, num_core_regs, vmstate):
        root = BodyTree()
        function.body = root

        oc = function.args[0]
        dc = Type["DeviceClass"].gen_var("dc", pointer = True)
        cc = Type["CPUClass"].gen_var("cc", pointer = True)
        mcc = Type[self.cpu.qom_cpu.struct_class_name()].gen_var("mcc",
            pointer = True
        )

        fn = self.cpu.qom_cpu.func_name

        root(
            Declare(
                OpAssign(dc, MCall("DEVICE_CLASS", oc))
            ),
            Declare(
                OpAssign(cc, MCall("CPU_CLASS", oc))
            ),
            Declare(
                OpAssign(
                    mcc,
                    MCall(
                        self.cpu.qom_cpu.class_macro(),
                        oc
                    )
                )
            ),
            OpAssign(
                OpSDeref(mcc, "parent_realize"),
                OpSDeref(dc, "realize")
            ),
            OpAssign(
                OpSDeref(dc, "realize"),
                Type[fn("realizefn")]
            ),
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
                    Type[self.cpu.qom_cpu.tcg_init_name()]
                )
            )

    def gen_cpu_realizefn(self, function):
        cs = Type["CPUState"].gen_var("cs", pointer = True)
        cc =  Type[self.cpu.qom_cpu.struct_class_name()].gen_var("cc",
            pointer = True
        )
        err = Type["Error"].gen_var("local_err", pointer = True)
        null = MCall("NULL")

        function.body = BodyTree()(
            Declare(
                OpAssign(
                    cs,
                    MCall("CPU", function.args[0])
                )
            ),
            Declare(
                OpAssign(
                    cc,
                    MCall(self.cpu.qom_cpu.get_class_macro(), function.args[0])
                )
            ),
            OpAssign(
                Declare(err),
                null
            ),
            Call(
                "cpu_exec_realizefn",
                cs,
                OpAddr(err)
            ),
            BranchIf(OpNEq(err, null))(
                Call(
                    "error_propagate",
                    function.args[1],
                    err
                ),
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

    def gen_cpu_initfn(self, function):
        root = BodyTree()
        function.body = root

        qtn = self.cpu.qom_cpu.qtn
        cs = Type["CPUState"].gen_var("cs", pointer = True)
        cpu = Type[self.cpu.qom_cpu.struct_name].gen_var("cpu",
            pointer = True
        )

        root(
            OpAssign(
                Declare(cs),
                MCall("CPU", function.args[0])
            ),
            OpAssign(
                Declare(cpu),
                MCall(
                    qtn.for_macros,
                    function.args[0]
                )
            )
        )

        if not get_vp("Generic call to tcg_initialize"):
            inited = Type["int"].gen_var("inited", static = True)
            root(Declare(inited))

        root(
            OpAssign(
                OpSDeref(cs, "env_ptr"),
                OpAddr(OpSDeref(cpu, "env"))
            )
        )

        if not get_vp("Generic call to tcg_initialize"):
            root(
                BranchIf(
                    OpLogAnd(
                        Call("tcg_enabled"),
                        OpLogNot(inited)
                    )
                )(
                    OpAssign(inited, 1),
                    Call(self.cpu.qom_cpu.tcg_init_name())
                )
            )

    def gen_class_by_name(self, function):
        oc = Type["ObjectClass"].gen_var("oc", pointer = True)
        cpu_model = function.args[0]
        null = MCall("NULL")

        function.body = BodyTree()(
            Declare(oc),
            BranchIf(OpEq(cpu_model, null))(
                Return(null)
            ),
            OpAssign(oc, Call("object_class_by_name", cpu_model)),
            BranchIf(
                OpLogAnd(
                    OpNEq(oc, null),
                        OpLogOr(
                            OpEq(
                                Call("object_class_dynamic_cast",
                                    oc,
                                    MCall(self.cpu.qom_cpu.qtn.type_macro)
                                ),
                                null
                            ),
                            Call("object_class_is_abstract", oc)
                    )
                )
            )(
                Return(null)
            ),
            Return(oc)
        )

    def gen_cpu_init(self, function):
        qtn = self.cpu.qom_cpu.qtn
        function.body = BodyTree()(
            Return(
                MCall(
                    qtn.for_macros,
                    Call(
                        "cpu_generic_init",
                        MCall(qtn.type_macro),
                        function.args[0]
                    )
                )
            )
        )

    def gen_tcg_init(self, function, reg_vars, cpu_env):
        root = BodyTree()
        function.body = root

        areg0 = cpu_env
        if get_vp("Init cpu_env in arch"):
            root(
                OpAssign(
                    areg0,
                    Call(
                        "tcg_global_reg_new_ptr",
                        MCall("TCG_AREG0"),
                        "env"
                    )
                ),
                OpAssign(
                    OpSDeref(Header["tcg.h"].global_variables["tcg_ctx"],
                        "tcg_env"
                    ),
                    areg0
                )
            )

        i = Type["int"].gen_var("i")
        root(Declare(i))

        cpu_arch_state = Type[self.cpu.qom_cpu.struct_state_name()]
        for r, reg_var, reg_name in reg_vars:
            if r.size <= 32:
                size = 32
            else:
                size = 64
            if isinstance(r, CPURegisterGroup):
                root(
                    LoopFor(OpAssign(i, 0), OpLower(i, len(r)), OpPredInc(i))(
                        OpAssign(
                            OpIndex(reg_var, i),
                            Call(
                                "tcg_global_mem_new_i" + str(size),
                                areg0,
                                MCall(
                                    "offsetof",
                                    cpu_arch_state,
                                    OpIndex(Node(r.name), i)
                                ),
                                OpIndex(reg_name, i)
                            )
                        )
                    )
                )
            else:
                name_var = r.name
                root(
                    OpAssign(
                        reg_var,
                        Call(
                            "tcg_global_mem_new_i" + str(size),
                            areg0,
                            MCall(
                                "offsetof",
                                cpu_arch_state,
                                Node(name_var)
                            ),
                            name_var
                        )
                    )
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

    def gen_cpu_register(self, function, info_var):
        function.body = BodyTree()(
            Call(
                "type_register_static",
                OpAddr(info_var)
            )
        )

    def gen_env_get_cpu(self, function):
        function.body = BodyTree()(
            Return(
                MCall(
                    "container_of",
                    function.args[0],
                    Type[self.cpu.qom_cpu.struct_name],
                    Node("env")
                )
            )
        )

    def gen_cpu_dump_state(self, function):
        root = BodyTree()
        function.body = root

        qom_cpu = self.cpu.qom_cpu
        cpu = Type[qom_cpu.struct_name].gen_var("cpu", pointer = True)
        env = Type[qom_cpu.struct_state_name()].gen_var("env", pointer = True)

        out_file = function.args[1]
        fprintf_func = function.args[2]
        i = Type["int"].gen_var("i")

        root(
            OpAssign(
                Declare(cpu),
                MCall(qom_cpu.qtn.for_macros, function.args[0])
            ),
            OpAssign(
                Declare(env),
                OpAddr(OpSDeref(cpu, "env"))
            ),
            Declare(i)
        )

        for rg in self.cpu.reg_groups:
            root(
                LoopFor(OpAssign(i, 0), OpLower(i, len(rg)), OpPredInc(i))(
                    Call(
                        fprintf_func,
                        out_file,
                        rg.name + "[%d]=0x%08x",
                        i,
                        OpIndex(OpSDeref(env, rg.name), i)
                    ),
                    BranchIf(OpEq(OpRem(i, 4), 3))(
                        Call(
                            fprintf_func,
                            out_file,
                            "\\n"
                        ),
                        BranchElse()(
                            Call(
                                fprintf_func,
                                out_file,
                                ' '
                            )
                        )
                    )
                )
            )

        for r in self.cpu.regs:
            root(
                Call(
                    fprintf_func,
                    out_file,
                    r.name + "=0x%08x\\n",
                    OpSDeref(env, r.name)
                )
            )

    def gen_cpu_get_tb_cpu_state(self, function):
        function.body = BodyTree()(
            OpAssign(
                OpDeref(function.args[1]),
                OpSDeref(function.args[0], "pc")
            ),
            OpAssign(OpDeref(function.args[2]), 0),
            OpAssign(OpDeref(function.args[3]), 0)
        )

    def gen_cpu_set_pc(self, function):
        qtn = self.cpu.qom_cpu.qtn
        cpu = Type[self.cpu.qom_cpu.struct_name].gen_var("cpu", pointer = True)

        function.body = BodyTree()(
            OpAssign(
                Declare(cpu),
                MCall(qtn.for_macros, function.args[0])
            ),
            OpAssign(
                OpSDeref(OpSDeref(cpu, "env"), "pc"),
                function.args[1]
            )
        )

    def gen_disas_set_info(self, function):
        function.body = BodyTree()(
            OpAssign(
                OpSDeref(function.args[1], "mach"),
                Type["bfd_architecture"].get_field(
                    "bfd_arch_" + self.cpu.target_name
                )
            ),
            OpAssign(
                OpSDeref(function.args[1], "print_insn"),
                Type["print_insn_" + self.cpu.target_name]
            )
        )

    def gen_helper_disas_write(self, function):
        function.body = BodyTree()(Return(0))

    def gen_handle_mmu_fault(self, function):
        prot = Type["int"].gen_var("prot")

        function.body = BodyTree()(
            Declare(
                OpAssign(prot,
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
                *(function.args[3:] + [ MCall("TARGET_PAGE_SIZE") ])
            ),
            Return(0)
        )

    def gen_raise_exception(self, function):
        s = Type["CPUState"].gen_var("s", pointer = True)

        function.body = BodyTree()(
            OpAssign(
                Declare(s),
                MCall(
                    "CPU",
                    Call(
                        self.cpu.qom_cpu.env_get_cpu_name(),
                        function.args[0]
                    )
                )
            ),
            OpAssign(
                OpSDeref(s, "exception_index"),
                function.args[1]
            ),
            Call("cpu_loop_exit", s)
        )

    def gen_helper_debug(self, function):
        function.body = BodyTree()(
            Call(
                "raise_exception",
                function.args[0],
                MCall("EXCP_DEBUG")
            )
        )

    def gen_helper_illegal(self, function):
        function.body = BodyTree()(
            Call(
                "raise_exception",
                function.args[0],
                Type["excp_enum"].get_field("EXCP_ILLEGAL")
            )
        )

    def gen_tlb_fill(self, function):
        ret = Type["int"].gen_var("ret")

        if get_vp("tlb_fill has SIZE argument"):
            args = [
                function.args[0],
                function.args[1],
                function.args[3],
                function.args[4]
            ]
        else:
            args = function.args[:-1]

        function.body = BodyTree()(
            OpAssign(
                Declare(ret),
                Call(
                    self.cpu.qom_cpu.func_name("handle_mmu_fault"),
                    *args
                )
            ),
            BranchIf(MCall("unlikely", ret))(
                Call(
                    "cpu_loop_exit_restore",
                    function.args[0], function.args[-1]
                )
            )
        )

    def gen_set_pc(self, function, pc):
        function.body = BodyTree()(OpAssign(pc, function.args[0]))

    def gen_restore_state_to_opc(self, function):
        function.body = BodyTree()(
            OpAssign(
                OpSDeref(function.args[0], "pc"),
                OpIndex(function.args[2], 0)
            )
        )

    def gen_cpu_mmu_index(self, function):
        function.body = BodyTree()(Return(0))

    def gen_get_phys_page_debug(self, function):
        function.body = BodyTree()(Return(function.args[1]))

    def gen_gdb_rw_register(self, function, comment):
        qom = self.cpu.qom_cpu
        cpu = Type[qom.struct_name].gen_var("cpu", pointer = True)
        cc = Type["CPUClass"].gen_var("cc", pointer = True)
        env = Type[qom.struct_state_name()].gen_var("env", pointer = True)

        ret_0 = Return(0)

        function.body = BodyTree()(
            Comment(comment),
            OpAssign(
                Declare(cpu),
                MCall(qom.qtn.for_macros, function.args[0])
            ),
            OpAssign(
                Declare(cc),
                MCall("CPU_GET_CLASS", function.args[0])
            ),
            OpAssign(
                Declare(env),
                OpAddr(OpSDeref(cpu, "env"))
            ),
            BranchIf(
                OpGreater(
                    function.args[2],
                    OpSDeref(cc, "gdb_num_core_regs")
                )
            )(
                ret_0
            ),
            ret_0
        )
