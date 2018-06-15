from c_generator import *
from .cpu import (
    RegisterGroup
)
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
    Variable as mVariable,
    Function as mFunction,
    Pointer as mPointer,
)
from qemu import (
    get_vp
)
from struct import (
    pack,
    unpack
)

from collections import OrderedDict

def byte_swap(i, len):
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

# this class contains glue utilities to get rid of
# direct C generator usage in arch creation code
class TargetCodeGenerator(object):
    def __init__(self, arch):
        self.arch = arch

    def gen_extract_field(self, res, var, offset, length, cur_read, prev_read):
        cur_offset = offset - prev_read * BYTE_SIZE
        if self.arch.byte_swap:
            be_byte_num = cur_offset // BYTE_SIZE
            le_byte_num = (cur_read - 1) - be_byte_num
            shift_val = cur_read * BYTE_SIZE - (le_byte_num * BYTE_SIZE +
                                   cur_offset % BYTE_SIZE + length)
        else:
            shift_val = cur_read * BYTE_SIZE - (cur_offset + length)

        if shift_val < 0:
            raise ValueError()
        op_shift = OpRShift(var, Const(shift_val))
        op_and = OpAnd(op_shift, Const(hex((1 << length) - 1)))
        op_res = OpAssign(res, op_and)

        return op_res

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
                        int(val) for val in findall('\d+', v.name)
                    ]
                    if var_off * BYTE_SIZE <= offset < offset + f.length \
                            <= var_off * BYTE_SIZE + var_len:
                        break
                    else:
                        try:
                            v = next(i)
                        except StopIteration:
                            raise Exception(
"Didn't find proper var for field at offset {} in {}".format(offset, instruction.mnem)
                            )
                else:
                    raise Exception(
"Didn't find proper var for field at offset {} in {}".format(offset, instruction.mnem)
                            )

                res = mVariable(
                    f.val + ':' + str(f.end) + ':' + str(f.start),
                    Type.lookup('uint64_t')
                )
                decl = self.gen_extract_field(
                    OpDeclare(res),
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
        #   OpDeclare       OpAnd
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
            same_vars = []
            same_vars.append(
                (d1.children[0].children[0].var, d1.children[1])
            )
            name1 = d1.children[0].children[0].var.name

            for d2 in decls:
                if d2 not in seen:
                    name2 = d2.children[0].children[0].var.name
                    i1 = name1.find(':')
                    i2 = name2.find(':')
                    if name1[:i1] == name2[:i2]:
                        same_vars.append(
                                (d2.children[0].children[0].var,
                                  d2.children[1]))
                        seen.append(d2)
            if len(same_vars) > 1:
                rval = None
                for t in same_vars:
                    v = t[0]
                    high, low = [int(val) for val
                            in findall('(?::)(\d+)', v.name)]
                    if rval is None:
                        rval = OpLShift(t[1], Const(low))
                    else:
                        rval = OpOr(rval, OpLShift(t[1], Const(low)))
                v = same_vars[0][0].name

                res = mVariable(v[:v.find(':') + 1], Type.lookup('uint64_t'))

                if res.name[-1] == ':':
                    res.name = res.name[0:(len(res.name) - 1)]
                res.name = res.name.replace(':', '_')
                new_decls.append(
                    OpAssign(
                        OpDeclare(
                            res,
                        ),
                        rval
                    )
                )
            else:
                ind = d1.children[0].children[0].var.name.find(':')
                d1.children[0].children[0].var.name = \
                    d1.children[0].children[0].var.name[:ind].replace(':', '_')
                new_decls.append(d1)

        for d in new_decls:
            node.add_child(d)
        return [d.children[0].children[0] for d in new_decls]

    def gen_field_read(self, node, offset, length, env, pc, already_read = 0,
                       is_opcode = False):
        byte_num = (offset + length) // BYTE_SIZE \
            + (1 if (offset + length) % BYTE_SIZE else 0)
        assert(byte_num >= 0)
        byte_num -= already_read
        if byte_num < 1:
            return None, 0
        sz_suffixes = {
            1: 'b',
            2: 'w',
            4: 'l',
            8: 'q'
        }
        sgn_suffixes = {
            'b': 'u',
            'w': 'u',
            'l': '',
            'q': ''
        }

        # need to read multiple of the read_size val
        byte_num = ceil(byte_num * 1.0 / self.arch.read_size) \
            * self.arch.read_size
        assert(byte_num <= 8)

        var_prefix = 'opc' if is_opcode else 'val'
        val = mVariable(
            var_prefix + str(already_read) + '_' + str(byte_num * BYTE_SIZE),
            Type.lookup('uint64_t')
        )
        expr = None
        prev_read = 0

        for k in range(0, int(log(byte_num, 2)) + 1):
            if byte_num & (1 << k):
                sz_suffix = sz_suffixes[1 << k]
                sgn_suffix = sgn_suffixes[sz_suffix]

                read = OpCall(
                    'cpu_ld' + sgn_suffix + sz_suffix + '_code',
                    env,
                    OpAdd(pc, Const(already_read + prev_read))
                )

                if expr is None:
                    expr = read
                else:
                    expr = OpOr(expr, OpLShift(read, prev_read << k))

                prev_read += 1
        assert(expr is not None)
        node.add_child(OpAssign(OpDeclare(val), expr))

        return val, byte_num

    def gen_decode_opc(self, function, cpu_pc, cpu_env):
        root = FunctionWrapper.connect(function)

        result = Type.lookup('int').gen_var('result')
        root.add_child(
            OpAssign(
                OpDeclare(result),
                Const(0)
            )
        )

        env = OpAddr(OpSDeref(function.args[0],
                                      Const('env')))

        ctx = function.args[1]
        ctx_pc = OpSDeref(ctx, Const('pc'))
        helper_funcs = []

        br_enum = Type.lookup('br_enum')
        tcg_gen_movi_tl = OpCall('tcg_gen_movi_tl', cpu_pc, ctx_pc)
        gen_helper_illegal = OpCall(
            'gen_helper_illegal',
            cpu_env,
            implicit_decl = True
        )
        ctx_bstate = OpSDeref(ctx, Const('bstate'))

        def handle_opc_iter(gen_node, instr_node, total_read, last_read = 0,
                            cur_vars = []):
            opc = instr_node.opcode
            opc_dict = OrderedDict(sorted(instr_node.opc_dict.items()))

            if instr_node.count > 1:
                new_var, cur_read = self.gen_field_read(
                    gen_node,
                    opc[0],
                    opc[1],
                    env,
                    ctx_pc,
                    total_read,
                    True
                )
                # new_var is None means cur_read = 0 and nothing was read
                # still should use variable read previously
                if new_var is None:
                    read_var = cur_vars[-1]
                    new_last_read = last_read
                else:
                    read_var = new_var
                    new_last_read = cur_read

                total_read += cur_read
                shift_val = total_read * BYTE_SIZE - (opc[0] + opc[1])
                shift_str = shift_val * '0'
                swap_size = new_last_read * BYTE_SIZE
                cases = []
                for k in opc_dict.keys():
                    if not k.isdigit():
                        continue
                    k += shift_str
                    if self.arch.byte_swap:
                        cases.append(
                            Const(hex(byte_swap(int(k, base = 2), swap_size)))
                        )
                    else:
                        cases.append(Const(hex(int(k, base = 2))))

                opc_mask = int('1' * opc[1], base = 2) << shift_val
                if self.arch.byte_swap:
                    opc_mask = byte_swap(opc_mask, swap_size)

                sw = BranchSwitch(
                    OpAnd(read_var, Const(hex(opc_mask))), cases = cases
                )
                # if opc_dict hasn't key 'default'
                # it means opc_dict hasn't instr_node with 'default' opc
                # and we must exit cpu loop in 'default' branch
                try:
                    check_default = opc_dict['default']
                except KeyError:
                    sw.bodies['default'].add_child(tcg_gen_movi_tl)
                    sw.bodies['default'].add_child(gen_helper_illegal)
                    sw.bodies['default'].add_child(
                        OpAssign(
                            ctx_bstate,
                            br_enum.get_field('BS_EXCP')
                        )
                    )
                gen_node.add_child(sw)

                for key, node in opc_dict.items():
                    if key.isdigit():
                        key += shift_str
                        if self.arch.byte_swap:
                            case_key = str(
                                hex(byte_swap(int(key, base = 2), swap_size))
                            )
                        else:
                            case_key = str(hex(int(key, base = 2)))
                    else:
                        case_key = 'default'
                    if new_var is not None:
                        new_vars = cur_vars + [new_var]
                    else:
                        new_vars = cur_vars
                    handle_opc_iter(
                        sw.bodies[case_key],
                        node,
                        total_read,
                        new_last_read,
                        new_vars
                    )
            else:
                if instr_node.instruction.comment is None:
                    mnem = instr_node.instruction.mnem
                    comm = Comment(mnem)
                else:
                    comm = Comment(instr_node.instruction.comment)
                gen_node.add_child(comm)

                new_var, new_read = self.gen_field_read(
                    gen_node,
                    total_read * BYTE_SIZE,
                    len(instr_node.instruction) - total_read * BYTE_SIZE,
                    env,
                    ctx_pc,
                    total_read
                )
                total_read += new_read
                if new_var is not None:
                    new_vars = cur_vars + [new_var]
                else:
                    new_vars = cur_vars

                opers = self.gen_extract_operands(
                    gen_node,
                    instr_node.instruction,
                    new_vars
                )

                instr_vars = []
                names_dict = {}
                for o in opers:
                    v = copy(o.var)
                    parts = o.var.name.split('_')
                    if len(parts) > 1:
                        try:
                            names_dict[parts[0]+parts[1]] += 1
                            parts[0] += str(names_dict[parts[0]+parts[1]])
                            print(
'Warning: auto-counter on the args of {} instruction'.format(instr_node.instruction.comment)
                            )
                        except KeyError:
                            names_dict.update({parts[0]+parts[1]: 1})

                        v.name = parts[0][0] \
                                 + (parts[0][-1] if parts[0][-1].isdigit() else '') \
                                 + parts[1]
                    else:
                        v.name = parts[0]
                    instr_vars.append(v)

                h = self.arch.gen_files['translate.inc.c']
                func = mFunction(
                    instr_node.instruction.name,
                    static = True,
                    inline = True,
                    body = '//' + instr_node.instruction.comment + '\n'
                )
                func.args = [
                    Type.lookup('DisasContext').gen_var('ctx', pointer = True)] \
                    + [v for v in instr_vars
                ]
                # add func to the list of fix-ordered helpers
                helper_funcs.append(func)
                h.add_type(func)

                helper_call = OpCall(instr_node.instruction.name, ctx, *opers)
                gen_node.add_child(helper_call)

                if self.arch.debug_decoder:
                    opers_str = '[' + instr_node.instruction.comment + ']('
                    for o in opers:
                        opers_str += '%lx, '
                    if opers_str[-1] == ' ':
                        opers_str = opers_str[:-2] + ')'
                    else:
                        opers_str += ')'
                    fprintf = OpCall(
                        'fprintf',
                        Const('stderr'),
                        Const('\"' + instr_node.instruction.name +
                              opers_str + '\\n\"'
                        ),
                        *opers
                    )
                    gen_node.add_child(fprintf)

                if instr_node.instruction.branch and not self.arch.debug_decoder:
                    gen_node.add_child(
                        OpAssign(
                            OpSDeref(ctx, Const('bstate')),
                            Type.lookup('br_enum').get_field('BS_BRANCH')
                        )
                    )

                gen_node.add_child(OpAssign(result, Const(total_read)))

        handle_opc_iter(root, self.arch.instr_tree_root, 0)
        # sort the helpers (can wait it to finish at the moment)
        # line_origins(helper_funcs)
        root.add_child(OpRet(result))

    def gen_disas_opcode_read(self,
            node,
            offset,
            length,
            addr,
            status,
            buf,
            info,
            already_read = 0,
            is_opcode = False
        ):

        byte_num = (offset + length) // BYTE_SIZE \
            + (1 if (offset + length) % BYTE_SIZE else 0)
        assert(byte_num >= 0)
        byte_num -= already_read
        if byte_num < 1:
            return None, 0

        # need to read multiple of the read_size val
        byte_num = ceil(byte_num * 1.0 / self.arch.read_size) \
            * self.arch.read_size
        assert(byte_num <= 8)

        read_memory_func = OpCall(
            OpSDeref(info, Const('read_memory_func')),
            OpAdd(
                addr,
                Const(already_read)
            ),
            buf,
            Const(byte_num),
            info
        )

        node.add_child(OpAssign(status, read_memory_func))
        if_status = BranchIf(status)
        if_status.add_child(Goto('fail'))

        node.add_child(if_status)

        if byte_num == 1:
            bfd_get = OpIndex(buf, Const('0'))
        else:
            suffix = 'b' if self.arch.arch_bigendian else 'l'
            suffix += str(byte_num * BYTE_SIZE)
            bfd_get = OpCall('bfd_get' + suffix, buf)


        var_prefix = 'opc' if is_opcode else 'val'
        val = mVariable(
            var_prefix + str(already_read) + '_' + str(byte_num * BYTE_SIZE),
            Type.lookup('uint64_t')
        )

        node.add_child(OpAssign(OpDeclare(val), bfd_get))

        return val, byte_num

    def gen_print_ins(self, function):
        root = FunctionWrapper.connect(function)

        status = mVariable('status', Type.lookup('int'))
        root.add_child(
            OpDeclare(status)
        )

        buffer = Type.lookup('bfd_byte').gen_var('buffer', array_size = 6)
        root.add_child(
            OpDeclare(buffer)
        )

        length = Type.lookup('int').gen_var('length')
        root.add_child(
            OpAssign(
                OpDeclare(length),
                Const(2)
            )
        )

        stream = Type.lookup('void').gen_var('stream', pointer = True)
        root.add_child(
            OpAssign(
                OpDeclare(stream),
                OpSDeref(
                    function.args[1],
                    Const('stream')
                )
            )
        )

        fpr = Type.lookup('fprintf_function').gen_var('fpr')
        root.add_child(
            OpAssign(
                OpDeclare(fpr),
                OpSDeref(
                    function.args[1],
                    Const('fprintf_func')
                )
            )
        )

        def handle_opc_iter(gen_node, instr_node, total_read, last_read = 0,
                            cur_vars = [], is_default = True):
            opc = instr_node.opcode
            opc_dict = OrderedDict(sorted(instr_node.opc_dict.items()))

            if instr_node.count > 1:
                new_var, cur_read = self.gen_disas_opcode_read(
                    gen_node,
                    opc[0],
                    opc[1],
                    function.args[0],
                    status,
                    buffer,
                    function.args[1],
                    total_read,
                    True
                )
                # new_var is None means cur_read = 0 and nothing was read
                # still should use variable read previously
                if new_var is None:
                    read_var = cur_vars[-1]
                    new_last_read = last_read
                else:
                    read_var = new_var
                    new_last_read = cur_read

                total_read += cur_read
                shift_val = total_read * BYTE_SIZE - (opc[0] + opc[1])
                shift_str = shift_val * '0'
                swap_size = new_last_read * BYTE_SIZE
                cases = []
                for k in opc_dict.keys():
                    if not k.isdigit():
                        continue
                    k += shift_str
                    if self.arch.byte_swap:
                        cases.append(
                            Const(hex(byte_swap(int(k, base = 2), swap_size)))
                        )
                    else:
                        cases.append(Const(hex(int(k, base = 2))))

                opc_mask = int('1' * opc[1], base = 2) << shift_val
                if self.arch.byte_swap:
                    opc_mask = byte_swap(opc_mask, swap_size)

                sw = BranchSwitch(
                    OpAnd(read_var,
                          Const(hex(opc_mask))
                    ),
                    cases = cases
                )
                # if opc_dict hasn't key 'default'
                # it means opc_dict hasn't instr_node with 'default' opc
                # and we must exit cpu loop in 'default' branch
                try:
                    check_default = opc_dict['default']
                except KeyError:
                    sw.bodies['default'].has_break = False
                    sw.bodies['default'].add_child(
                        OpCall('fprintf',
                               Const('stderr'),
                               Const('\"' + 'Unknown@binstruction'
                                         + '\\n\"'))
                    )
                    sw.bodies['default'].add_child(
                       OpCall('abort')
                    )
                gen_node.add_child(sw)

                for key, node in opc_dict.items():
                    if key.isdigit():
                        key += shift_str
                        if self.arch.byte_swap:
                            case_key = str(
                                hex(byte_swap(int(key, base = 2), swap_size))
                            )
                        else:
                            case_key = str(hex(int(key, base = 2)))
                    else:
                        case_key = 'default'
                    if new_var is not None:
                        new_vars = cur_vars + [new_var]
                    else:
                        new_vars = cur_vars
                    handle_opc_iter(
                        sw.bodies[case_key],
                        node,
                        total_read,
                        new_last_read,
                        new_vars,
                        case_key == 'default'
                    )
            else:
                if instr_node.instruction.comment is None:
                    mnem = instr_node.instruction.mnem
                    comm = Comment(mnem)
                else:
                    comm = Comment(instr_node.instruction.comment)
                gen_node.add_child(comm)
                if is_default:
                    print(
                        'Warning: "%s" arguments intersect with the opcode' %
                        comm.value
                    )

                new_var, new_read = self.gen_disas_opcode_read(
                    gen_node,
                    total_read * BYTE_SIZE,
                    len(instr_node.instruction) - total_read * BYTE_SIZE,
                    function.args[0],
                    status,
                    buffer,
                    function.args[1],
                    total_read
                )
                total_read += new_read
                if new_var is not None:
                    new_vars = cur_vars + [new_var]
                else:
                    new_vars = cur_vars

                self.gen_extract_operands(
                    gen_node,
                    instr_node.instruction,
                    new_vars
                )

                format_line = ''
                opers_call = []
                name_to_format = self.arch.name_to_format
                for m in finditer('<(.+?)>|([^<>]+)', instr_node.instruction.format):
                    try:
                        gr = m.group(1)
                        v = name_to_format[gr]
                        gr = ', '.join(map(
                            (lambda x: x.strip().split('$')[0]),
                            gr.split(',')
                        ))

                        if v[0] is not None:
                            param = v[0]
                        else:
                            if format_line:
                                fprintf = OpCall(
                                    fpr,
                                    Const('stream'),
                                    Const('"' + format_line + '"'),
                                    *opers_call
                                )
                                gen_node.add_child(fprintf)

                                print_func = OpCall(
                                    v[1],
                                    fpr,
                                    Const('stream'),
                                    Const(gr)
                                )
                                gen_node.add_child(print_func)

                                format_line = ''
                                opers_call = []
                            continue

                        if v[1] is not None:
                            opers_call.append(OpCall(v[1], Const(gr)))
                        else:
                            opers_call.append(Const('(unsigned) ' + gr))
                    except KeyError:
                        param = m.group(0)
                    format_line += param

                if format_line:
                    fprintf = OpCall(
                        fpr,
                        Const('stream'),
                        Const('"' + format_line + '"'),
                        *opers_call
                    )
                    gen_node.add_child(fprintf)

                gen_node.add_child(OpAssign(length, Const(total_read)))

        handle_opc_iter(root, self.arch.instr_tree_root, 0)
        root.add_child(OpRet(length))

        root.add_child(Const('fail:\n'))
        memory_error_func = OpCall(
            OpSDeref(function.args[1], Const('memory_error_func')),
            status, function.args[0], function.args[1]
        )
        root.add_child(memory_error_func)
        root.add_child(OpRet(Const('-1')))

    def gen_gen_intermediate_code(self, function, cpu_pc, cpu_env):
        root = FunctionWrapper.connect(function)

        if get_vp()['gen_intermediate_code arg1 is generic']:
            env_type = self.arch.target_cpu.get_cpustate_name() 
            env = Type.lookup(env_type).gen_var('env', pointer = True)
            root.add_child(
                OpAssign(
                    OpDeclare(env),
                    OpSDeref(function.args[0], Const('env_ptr'))
                )
            )
        else:
            env = function.args[0]

        cpu = Type.lookup(self.arch.name.upper() + 'CPU')\
            .gen_var('cpu', pointer = True)

        root.add_child(
            OpAssign(
                OpDeclare(cpu),
                OpCall(self.arch.name + '_env_get_cpu', env)
            )
        )

        br_enum = Type.lookup('br_enum')
        ctx = mVariable('ctx', Type.lookup('DisasContext'))
        ctx_pc = OpSDeref(ctx, Const('pc'))
        ctx_tb = OpSDeref(ctx, Const('tb'))
        tcg_gen_movi_tl = OpCall('tcg_gen_movi_tl', cpu_pc, ctx_pc)
        gen_helper_debug = OpCall(
            'gen_helper_debug',
            cpu_env,
            implicit_decl = True
        )
        ctx_bstate = OpSDeref(ctx, Const('bstate'))

        tb = function.args[1]

        if not get_vp()['gen_intermediate_code arg1 is generic']:
            cs = Type.lookup('CPUState').gen_var('cs', pointer = True)
            root.add_child(
                OpAssign(
                    OpDeclare(cs),
                    OpMCall('CPU', cpu)
                )
            )
        else:
            cs = function.args[0]

        bp = Type.lookup('CPUBreakpoint').gen_var('bp', pointer = True)
        root.add_child(OpDeclare(bp))

        pc_start = Type.lookup('int').gen_var('pc_start')
        root.add_child(OpDeclare(pc_start))

        num_insns = Type.lookup('int').gen_var('num_insns')
        max_insns = Type.lookup('int').gen_var('max_insns')

        root.add_child(OpDeclare(num_insns, max_insns))
        root.add_child(OpAssign(num_insns, Const(0)))
        root.add_child(OpAssign(
            max_insns,
            OpAnd(
                OpSDeref(tb, Const('cflags')),
                OpMCall('CF_COUNT_MASK')
            )
        ))
        root.add_child(OpDeclare(ctx))
        root.add_child(
            OpAssign(
                ctx_bstate,
                br_enum.get_field('BS_NONE')
            )
        )

        if1 = BranchIf(OpEq(max_insns, Const(0)))
        if1.add_child(OpAssign(
            max_insns, OpMCall('CF_COUNT_MASK')
        ))
        root.add_child(if1)

        if2 = BranchIf(
            OpGreater(max_insns, OpMCall('TCG_MAX_INSNS'))
        )
        if2.add_child(OpAssign(max_insns, OpMCall('TCG_MAX_INSNS')))
        root.add_child(if2)

        root.add_child(
            OpAssign(pc_start, OpSDeref(tb, Const('pc')))
        )
        root.add_child(OpAssign(ctx_pc, pc_start))
        root.add_child(OpAssign(ctx_tb, tb))
        root.add_child(OpCall('gen_tb_start', tb))

        loop = LoopDoWhile(
            OpLogAnd(
                OpLogNot(OpCall('tcg_op_buf_full')),
                OpEq(ctx_bstate,
                         br_enum.get_field('BS_NONE'))
            )
        )

        cs_bp = OpAddr(OpSDeref(cs, Const('breakpoints')))
        qtail = OpMCall(
            'QTAILQ_FOREACH',
            bp,
            cs_bp,
            Const('entry')
        )
        mloop = MacroBranch(qtail)

        if_ctx_pc = BranchIf(
            OpEq(
                ctx_pc,
                OpSDeref(bp, Const('pc'))
            )
        )
        if_ctx_pc.add_child(tcg_gen_movi_tl)
        if_ctx_pc.add_child(gen_helper_debug)
        if_ctx_pc.add_child(
            OpAssign(
                ctx_bstate,
                br_enum.get_field('BS_EXCP')
            )
        )
        if_ctx_pc.add_child(Goto('done_generating'))

        mloop.add_child(if_ctx_pc)

        unlikely = BranchIf(
            OpMCall(
                'unlikely',
                OpLogNot(OpMCall(
                    'QTAILQ_EMPTY',
                    cs_bp
                ))
            )
        )
        unlikely.add_child(mloop)

        loop.add_child(unlikely)
        loop.add_child(OpCall('tcg_gen_insn_start', ctx_pc))
        loop.add_child(
            OpAssign(
                ctx_pc,
                OpAdd(
                    ctx_pc,
                    OpCall('decode_opc', cpu, OpAddr(ctx))
                )
            )
        )
        loop.add_child(OpAssign(num_insns,
                                    OpAdd(num_insns, Const(1))))

        lif1 = BranchIf(OpGE(num_insns, max_insns))
        lif1.add_child(OpBreak())
        loop.add_child(lif1)

        lif2 = BranchIf(OpEq(
            OpAnd(
                ctx_pc,
                OpSub(
                    OpMCall('TARGET_PAGE_SIZE'),
                    Const(1),
                    parenthesis = True
                ),
            ),
            Const(0)
        ))
        lif2.add_child(OpBreak())
        loop.add_child(lif2)

        lif3 = BranchIf(OpSDeref(cs, Const('singlestep_enabled')))
        lif3.add_child(OpBreak())
        loop.add_child(lif3)

        root.add_child(loop)

        check_bstate = BranchIf(
            OpLogOr(
                OpEq(ctx_bstate, br_enum.get_field('BS_NONE')),
                OpEq(ctx_bstate, br_enum.get_field('BS_STOP')),
            )
        )
        check_bstate.add_child(tcg_gen_movi_tl)

        if_singlestep = BranchIf(OpSDeref(cs, Const('singlestep_enabled')))
        if_singlestep.add_child(check_bstate)
        if_singlestep.add_child(gen_helper_debug)
        root.add_child(if_singlestep)

        bstate_switch = BranchSwitch(
            OpSDeref(ctx, Const('bstate')),
            add_breaks = False,
            cases = [
                Const('BS_STOP'),
                Const('BS_NONE'),
                Const('BS_EXCP'),
                Const('BS_BRANCH')
            ],
        )
        case_none = bstate_switch.bodies['BS_NONE']
        case_none.add_child(tcg_gen_movi_tl)
        case_none.has_break = True
        bstate_switch.bodies['default'].has_break = True

        else_singlestep = BranchElse()
        else_singlestep.add_child(bstate_switch)
        else_singlestep.add_child(OpCall('tcg_gen_exit_tb', Const(0)))

        if_singlestep.add_else(else_singlestep)

        root.add_child(Const('done_generating:\n'))
        root.add_child(OpCall('gen_tb_end', tb, num_insns))
        root.add_child(
            OpAssign(
                OpSDeref(tb, Const('size')),
                OpSub(ctx_pc, pc_start)
            )
        )
        root.add_child(
            OpAssign(
                OpSDeref(tb, Const('icount')),
                num_insns
            )
        )

        # Disas
        root.add_child(Const('#ifdef DEBUG_DISAS\n'))
        if_block = BranchIf(
            OpLogAnd(
                OpCall(
                    'qemu_loglevel_mask',
                    OpMCall('CPU_LOG_TB_IN_ASM')
                ),
                OpCall(
                    'qemu_log_in_addr_range',
                    pc_start
                )
            )
        )
        if_block.add_child(
            OpCall('qemu_log_lock')
        )
        if_block.add_child(
            OpCall(
                'qemu_log',
                Const('"IN: %s\\n"'),
                OpCall('lookup_symbol', pc_start)
            )
        )
        target_disas_args = [cs, pc_start, OpSub(ctx_pc, pc_start)]
        if get_vp()['target_disas has FLAGS argument']:
            target_disas_args.append(Const('0'))
        if_block.add_child(
            OpCall(
                'log_target_disas',
                *target_disas_args
            )
        )
        if_block.add_child(
            OpCall(
                'qemu_log',
                Const('"\\n"')
            )
        )
        if_block.add_child(
            OpCall('qemu_log_unlock')
        )
        root.add_child(if_block)
        root.add_child(Const('#endif\n'))

    def gen_cpu_class_initfn(self, function, num_core_regs, vmstate):
        root = FunctionWrapper.connect(function)

        oc = function.args[0]
        dc = Type.lookup('DeviceClass').gen_var('dc', pointer = True)
        cc = Type.lookup('CPUClass').gen_var('cc', pointer = True)
        mcc = Type.lookup(
            self.arch.target_cpu.get_cpu_name() + 'Class'
        ).gen_var('mcc', pointer = True)

        root.add_child(OpDeclare(
            OpAssign(dc, OpMCall('DEVICE_CLASS', oc))))
        root.add_child(OpDeclare(
            OpAssign(cc, OpMCall('CPU_CLASS', oc))))
        root.add_child(OpDeclare(
                OpAssign(
                    mcc,
                    OpMCall(
                        self.arch.name.upper() + '_CPU_CLASS',
                        oc
                    )
                )
        ))
        root.add_child(OpAssign(
            OpSDeref(mcc, Const('parent_realize')),
            OpSDeref(dc, Const('realize'))
        ))
        root.add_child(OpAssign(
            OpSDeref(dc, Const('realize')),
            Const(Type.lookup(self.arch.name + '_cpu_realizefn').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(mcc, Const('parent_reset')),
            OpSDeref(cc, Const('reset'))
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('reset')),
            Const(Type.lookup(self.arch.name + '_cpu_reset').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('has_work')),
            Const(Type.lookup(self.arch.name + '_cpu_has_work').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('do_interrupt')),
            Const(Type.lookup(self.arch.name + '_cpu_do_interrupt').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('set_pc')),
            Const(Type.lookup(self.arch.name + '_cpu_set_pc').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('dump_state')),
            Const(Type.lookup(self.arch.name + '_cpu_dump_state').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('disas_set_info')),
            Const(Type.lookup(self.arch.name + '_cpu_disas_set_info').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('class_by_name')),
            Const(Type.lookup(self.arch.name + '_cpu_class_by_name').name)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('vmsd')),
            OpAddr(vmstate)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('gdb_num_core_regs')),
            Const(num_core_regs)
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('gdb_read_register')),
            Const(
                Type.lookup(
                    self.arch.name + '_cpu_gdb_read_register'
                ).name
            )
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('gdb_write_register')),
            Const(
                Type.lookup(
                    self.arch.name + '_cpu_gdb_write_register'
                ).name
            )
        ))
        root.add_child(OpAssign(
            OpSDeref(cc, Const('get_phys_page_debug')),
            Const(
                Type.lookup(
                    self.arch.name + '_cpu_get_phys_page_debug'
                ).name
            )
        ))
        if get_vp()['Generic call to tcg_initialize']:
            root.add_child(OpAssign(
                OpSDeref(cc, Const('tcg_initialize')),
                Const(
                    Type.lookup(
                        self.arch.name + '_tcg_init'
                    ).name
                )
            ))

    def gen_cpu_realizefn(self, function):
        root = FunctionWrapper.connect(function)

        cs = Type.lookup('CPUState').gen_var('cs', pointer = True)
        arch = self.arch.name.upper()
        cc =  Type.lookup(arch + 'CPUClass').gen_var('cc', pointer = True)

        root.add_child(
            OpDeclare(
                OpAssign(
                    cs,
                    OpMCall('CPU', function.args[0])
                )
            )
        )

        root.add_child(
            OpDeclare(
                OpAssign(
                    cc,
                    OpMCall(arch + '_CPU_GET_CLASS', function.args[0])
                )
            )
        )

        err = Type.lookup('Error').gen_var('local_err', pointer = True)
        root.add_child(OpAssign(
            OpDeclare(err),
            Const('NULL')
            )
        )

        root.add_child(
            OpCall(
                'cpu_exec_realizefn',
                cs,
                OpAddr(err)
            )
        )

        br = BranchIf(
            OpNEq(err, Const('NULL'))
        )
        br.add_child(
            OpCall(
                'error_propagate',
                function.args[1],
                err
            )
        )
        br.add_child(OpRet())
        root.add_child(br)

        root.add_child(OpCall('qemu_init_vcpu', cs))
        root.add_child(OpCall('cpu_reset', cs))
        root.add_child(
            OpCall(
                OpSDeref(cc, Const('parent_realize')),
                function.args[0],
                function.args[1]
            )
        )

    # TODO: implement cs->env_ptr = &cpu->env
    # it needs structure field access operators: . and ->
    def gen_cpu_initfn(self, function):
        root = FunctionWrapper.connect(function)

        cs = Type.lookup('CPUState').gen_var('cs', pointer = True)

        cpu = Type.lookup(
            self.arch.name.upper() + 'CPU'
        ).gen_var('cpu', pointer = True)

        root.add_child(
            OpAssign(
                OpDeclare(cs),
                OpMCall('CPU', function.args[0])
            )
        )
        root.add_child(
            OpAssign(
                OpDeclare(cpu),
                OpMCall(
                    self.arch.name.upper() + '_CPU',
                    function.args[0]
                )
            )
        )

        if not get_vp()['Generic call to tcg_initialize']:
            inited = Type.lookup('int').gen_var('inited', static = True)
            root.add_child(OpDeclare(inited))

        root.add_child(
            OpAssign(
                OpSDeref(cs, Const('env_ptr')),
                OpAddr(OpSDeref(cpu, Const('env')))
            )
        )

        if not get_vp()['Generic call to tcg_initialize']:
            br = BranchIf(
                OpLogAnd(
                    OpCall('tcg_enabled'),
                    OpLogNot(inited)
                )
            )
            root.add_child(br)
            br.add_child(OpAssign(inited, Const(1)))
            br.add_child(OpCall(self.arch.name + '_tcg_init'))

    def gen_class_by_name(self, function):
        root = FunctionWrapper.connect(function)

        oc = mPointer(Type.lookup('ObjectClass')).gen_var('oc')
        decl_oc = OpDeclare(oc)
        null = Const('NULL')

        cpu_model = function.args[0]

        root.add_child(decl_oc)

        check_null = BranchIf(
            OpEq(cpu_model, null)
        )
        root.add_child(check_null)
        check_null.add_child(OpRet(null))
        root.add_child(
            OpAssign(oc, OpCall('object_class_by_name', cpu_model))
        )
        check = BranchIf(
            OpLogAnd(
                OpNEq(oc, null),
                    OpLogOr(
                        OpEq(
                            OpCall('object_class_dynamic_cast',
                                oc,
                                Const(
                                    Type.lookup(
                                        'TYPE_' + self.arch.name.upper() + '_CPU'
                                        ).gen_usage_string())
                                ),
                            null
                        ),
                        OpCall('object_class_is_abstract', oc)
                )
            )
        )
        root.add_child(check)
        check.add_child(OpRet(null))

        root.add_child(OpRet(oc))

    def gen_cpu_init(self, function):
        root = FunctionWrapper.connect(function)

        root.add_child(OpRet(
            OpMCall(
                self.arch.name.upper() + '_CPU',
                OpCall(
                    'cpu_generic_init',
                    Const('TYPE_' + self.arch.name.upper() + '_CPU'),
                    function.args[0]
                )
            )
        ))

    def gen_tcg_init(self, function, reg_vars, cpu_env):
        root = FunctionWrapper.connect(function)

        areg0 = cpu_env
        if get_vp()["Init cpu_env in arch"]:
            root.add_child(OpAssign(
                areg0,
                OpCall(
                    'tcg_global_reg_new_ptr',
                        Const('TCG_AREG0'),
                        Const('\"env\"')
                )
            ))

            root.add_child(
                OpAssign(
                    Const('tcg_ctx.tcg_env'),
                    areg0
                )
            )

        i = mVariable('i', Type.lookup('int'))
        decl_i = OpDeclare(i)
        root.add_child(decl_i)

        r_zip = zip(
            self.arch.target_cpu.reg_groups + self.arch.target_cpu.regs,
            reg_vars
        )
        for r, reg_var in r_zip:
            if isinstance(r, RegisterGroup):
                name_var = Type.lookup(
                    'const char'
                ).gen_var(r.name, pointer = True, array_size = len(r))
                names_vals = '{\n'
                for r1 in r.regs:
                    names_vals += '\"' + r1.name + '\",'
                names_vals += '}'
                root.add_child(
                    OpAssign(
                        OpDeclare(name_var),
                        Const(names_vals)
                    )
                )
                loop = LoopFor(
                    i,
                    0,
                    OpLower(i, Const(len(r))),
                    1
                )
                root.add_child(loop)
                if r.size <= 32:
                    size = 32
                else:
                    size = 64
                loop.add_child(OpAssign(
                    OpIndex(reg_var, i),
                    OpCall(
                        'tcg_global_mem_new_i' + str(size),
                        areg0,
                        OpMCall(
                            'offsetof',
                            Const('CPU' + self.arch.name.upper() + 'State'),
                            mVariable(
                                r.name + '[' + i.name + ']',
                                Type.lookup('int')
                            )),
                        OpIndex(name_var, i)
                    )
                ))
            else:
                name_var = Const('\"' + r.name + '\"')
                if r.size <= 32:
                    size = 32
                else:
                    size = 64
                root.add_child(
                    OpAssign(
                        reg_var,
                        OpCall(
                            'tcg_global_mem_new_i' + str(size),
                            areg0,
                            OpMCall(
                                'offsetof',
                                Const('CPU' + self.arch.name.upper() + 'State'),
                                Type.lookup('int').gen_var(r.name)
                                ),
                            name_var
                        )
                    )
                )

    def gen_cpu_has_work(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(OpRet(
            OpAnd(
                OpSDeref(function.args[0], Const('interrupt_request')),
                OpMCall('CPU_INTERRUPT_HARD')
            )
        ))

    def gen_cpu_register(self, function, info_var):
        root = FunctionWrapper.connect(function)
        root.add_child(
            OpCall('type_register_static',
                       OpAddr(info_var))
        )

    def gen_env_get_cpu(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(
            OpRet(
                OpMCall(
                    'container_of',
                    function.args[0],
                    Const(self.arch.name.upper() + 'CPU'),
                    Const('env')
                )
            )
        )

    def gen_cpu_dump_state(self, function, target_cpu):
        root = FunctionWrapper.connect(function)
        cpu = Type.lookup(self.arch.name.upper() + 'CPU')\
            .gen_var('cpu', pointer = True)
        env = Type.lookup('CPU' + self.arch.name.upper() + 'State')\
            .gen_var('env', pointer = True)
        out_file = function.args[1]
        fprintf_func = function.args[2]

        root.add_child(
            OpAssign(
                OpDeclare(cpu),
                OpMCall(self.arch.name.upper() + '_CPU', function.args[0])
            )
        )
        root.add_child(
            OpAssign(
                OpDeclare(env),
                OpAddr(OpSDeref(cpu, env))
            )
        )
        i = Type.lookup('int').gen_var('i')
        root.add_child(OpDeclare(i))

        for rg in target_cpu.reg_groups:
            loop = LoopFor(i, 0, OpLower(i, Const(len(rg))), 1)
            loop.add_child(
                OpCall(
                    fprintf_func,
                    out_file,
                    Const('\"' + rg.name + '[%d]=0x%08x \"'),
                    i,
                    OpIndex(
                        OpSDeref(env, Const(rg.name)),
                        i
                    )
                )
            )
            if_ctx = BranchIf(
                OpEq(
                    OpRem(i, Const(4)),
                    Const(3)
                )
            )
            if_ctx.add_child(OpCall(fprintf_func,
                                        out_file,
                                        Const('\"\\n\"')))
            loop.add_child(if_ctx)
            root.add_child(loop)
        for r in target_cpu.regs:
            root.add_child(
                OpCall(
                    fprintf_func,
                    function.args[1],
                    Const('\"' + r.name + '=0x%08x\\n\"'),
                    OpSDeref(env, Const(r.name))
                )
            )

    def gen_cpu_get_tb_cpu_state(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(
            OpAssign(
                OpDeref(function.args[1]),
                OpSDeref(function.args[0], Const('pc'))
            )
        )
        root.add_child(
            OpAssign(
                OpDeref(function.args[2]),
                Const(0)
            )
        )
        root.add_child(
            OpAssign(
                OpDeref(function.args[3]),
                Const(0)
            )
        )

    def gen_cpu_set_pc(self, function):
        root = FunctionWrapper.connect(function)
        cpu = Type.lookup(self.arch.name.upper() + 'CPU')\
            .gen_var('cpu', pointer = True)

        root.add_child(
            OpAssign(
                OpDeclare(cpu),
                OpMCall(self.arch.name.upper() + '_CPU',
                            function.args[0])
            )
        )
        root.add_child(
            OpAssign(
                OpSDeref(cpu, Const('env.pc')),
                function.args[1]
            )
        )

    def gen_disas_set_info(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(
            OpAssign(
                OpSDeref(function.args[1], Const('mach')),
                # actually bdf_arch_* is a part of enum,
                # bus now enums aren't supported
                Const('bfd_arch_' + self.arch.name)
            )
        )
        root.add_child(
            OpAssign(
                OpSDeref(function.args[1], Const('print_insn')),
                Const('print_insn_' + self.arch.name)
            )
        )

    def gen_helper_disas_write(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(OpRet(Const('0')))

    def gen_handle_mmu_fault(self, function):
        root = FunctionWrapper.connect(function)
        addr = function.args[1]
        prot = Type.lookup('int').gen_var('prot')
        root.add_child(
            OpDeclare(
                OpAssign(prot,
                    OpOr(
                        OpMCall('PAGE_READ'),
                        OpOr(
                            OpMCall('PAGE_WRITE'),
                            OpMCall('PAGE_EXEC')
                        )
                    )
                )
            )
        )
        root.add_child(
            OpAssign(
                addr,
                OpAnd(
                    addr,
                    OpMCall('TARGET_PAGE_MASK')
                )
            )
        )
        root.add_child(OpCall(
            'tlb_set_page',
            *(function.args[0:2] +
              [function.args[1], prot] +
              function.args[3:] +
              [OpMCall('TARGET_PAGE_SIZE')]
              )
        ))
        root.add_child(OpRet(Const(0)))

    def gen_raise_exception(self, function):
        root = FunctionWrapper.connect(function)

        s = Type.lookup('CPUState').gen_var('s', pointer = True)
        root.add_child(
            OpAssign(
                OpDeclare(s),
                OpMCall(
                    'CPU',
                    OpCall(
                        self.arch.name + '_env_get_cpu',
                        function.args[0]
                    )
                )
            )
        )

        root.add_child(
            OpAssign(
                OpSDeref(s, Const('exception_index')),
                function.args[1]
            )
        )

        root.add_child(
            OpCall(
                'cpu_loop_exit',
                s
            )
        )

    def gen_helper_debug(self, function):
        root = FunctionWrapper.connect(function)

        root.add_child(
            OpCall(
                'raise_exception',
                function.args[0],
                OpMCall('EXCP_DEBUG')
            )
        )

    def gen_helper_illegal(self, function):
        root = FunctionWrapper.connect(function)

        root.add_child(
            OpCall(
                'raise_exception',
                function.args[0],
                Type.lookup('excp_enum').get_field('EXCP_ILLEGAL')
            )
        )

    def gen_tlb_fill(self, function):
        root = FunctionWrapper.connect(function)

        ret = Type.lookup('int').gen_var('ret')
        root.add_child(
            OpAssign(
                OpDeclare(ret),
                OpCall(
                    self.arch.name + '_cpu_handle_mmu_fault',
                    function.args[0],
                    function.args[1],
                    function.args[3],
                    function.args[4]
                )
            )
        )

        unlikely = BranchIf(OpMCall('unlikely', ret))
        unlikely.add_child(OpCall('cpu_loop_exit_restore', function.args[0],
                                      function.args[-1]))
        root.add_child(unlikely)

    def gen_restore_state_to_opc(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(
            OpAssign(
                OpSDeref(function.args[0], Const('pc')),
                OpIndex(function.args[2], Const(0))
            )
        )

    def gen_cpu_mmu_index(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(OpRet(Const(0)))

    def gen_get_phys_page_debug(self, function):
        root = FunctionWrapper.connect(function)
        root.add_child(OpRet(function.args[1]))

    def gen_gdb_rw_register(self, function, comment):
        root = FunctionWrapper.connect(function)

        ret_0 = OpRet(Const('0'))

        root.add_child(Comment(comment))

        cpu = Type.lookup(
            self.arch.name.upper() + 'CPU'
        ).gen_var('cpu', pointer = True)

        cc = Type.lookup(
            'CPUClass'
        ).gen_var('cc', pointer = True)

        env = Type.lookup(
            'CPU' + self.arch.name.upper() + 'State'
        ).gen_var('env __attribute__((unused))', pointer = True)

        root.add_child(
            OpAssign(
                OpDeclare(cpu),
                OpMCall(self.arch.name.upper() + '_CPU', function.args[0])
            )
        )
        root.add_child(
            OpAssign(
                OpDeclare(cc),
                OpMCall('CPU_GET_CLASS', function.args[0])
            )
        )
        root.add_child(
            OpAssign(
                OpDeclare(env),
                OpAddr(OpSDeref(cpu, Const('env')))
            )
        )

        check_num = BranchIf(
            OpGreater(
                function.args[2],
                OpSDeref(cc, Const('gdb_num_core_regs'))
            )
        )
        check_num.add_child(ret_0)
        root.add_child(check_num)

        root.add_child(ret_0)
