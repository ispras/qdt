# XXX: code_generation.py: implement glue functions to get rid of direct body tree filling in cpu creation code
#      -> qemu.cpu: functions filling CPU & TCG front-end implementation
# XXX: to dedicated module
__all__ = [
    "fill_bfd_getb64_body"
  , "fill_class_by_name_body"
  , "fill_class_init_body"
  , "fill_cpu_get_tb_cpu_state_body"
  , "fill_cpu_init_body"
  , "fill_cpu_mmu_index_body"
  , "fill_cpuclass_tlb_fill_body"
  , "fill_decode_opc_body"
  , "fill_disas_set_info_body"
  , "fill_disas_write_helper_body"
  , "fill_dump_state_body"
  , "fill_env_get_cpu_body"
  , "fill_gdb_rw_register_body"
  , "fill_gen_intermediate_code_body"
  , "fill_get_phys_page_debug_body"
  , "fill_handle_mmu_fault_body"
  , "fill_has_work_body"
  , "fill_helper_debug_body"
  , "fill_helper_illegal_body"
  , "fill_initfn_body"
  , "fill_print_insn_body"
  , "fill_raise_exception_body"
  , "fill_realizefn_body"
  , "fill_reset_body"
  , "fill_restore_state_to_opc_body"
  , "fill_set_pc_body"
  , "fill_set_pc_inc_body"
  , "fill_tcg_init_body"
  , "fill_tlb_fill_body"
]

from ..version import (
    get_vp,
)
from .constants import (
    BYTE_SIZE,
    OPERAND_MAX_SIZE,
)
from collections import (
    defaultdict,
)
from common import (
    ee,
)
from copy import (
    copy,
)
from itertools import (
    count,
)
from re import (
    finditer,
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
    Variable,
)


DEBUG_DECODER = ee("QDT_DEBUG_DECODER")


class ParseTreeCodeBuilder(object):
    "This class traverses the instruction tree and builds the parsing code."

    def __init__(self, cputype, gen_node, gen_field_read_cb, epilogue_cb,
        result, default_switch_case_nodes,
        add_break = True
    ):
        # XXX: add argument description, only `cputype` is self explanatory
        instruction_tree_root = cputype.instruction_tree_root
        if not instruction_tree_root:
            gen_node(*default_switch_case_nodes)
            return

        self.target_bigendian = cputype.target_bigendian
        self.read_size = cputype.read_size
        self.gen_field_read_cb = gen_field_read_cb
        self.epilogue_cb = epilogue_cb
        self.result = result
        self.default_switch_case = SwitchCaseDefault(add_break = add_break)(
            *default_switch_case_nodes
        )

        # divide vars by purpose
        self.opcode_vars = set()
        self.operands_vars = set()
        self.vars = set()

        self.gen_subtree_code(gen_node, instruction_tree_root)

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
            # Note, the variable name starts with a digit but the variable will
            # be renamed by adding the purpose prefix at the end of the code
            # build.
            # XXX: alternative
            # A variable name can't start with a digit but a semantic prefix
            # will be assigned at end of code generation.
            val = Type["uint64_t"]("%d_%d" % (offset // BYTE_SIZE, length))
            val_desc = (val, offset, length)
            vals.append(val_desc)
            self.gen_field_read_cb(node, *val_desc)

        return vals

    # XXX: у этих функций понимание аргументов зависит от контекста, где
    #      эти функции используются. Их лучше расставить в порядке углубления.
    #      Порядок от простого к составному ту не годится.
    def calc_shift_val(self, var_offset, var_length, offset, length):
        # XXX: нужно подумать над порядком изложения, приходится прочитать до
        #      конца, а потом ещё пару раз, чтобы понять начало: при чём тут
        #      вообще порядок байт.
        # Bytes in memory (address indicated):
        # [ 0 ][ 1 ][ 2 ][ 3 ]
        # XXX: это это за байты? 4-байтовая инструкция?
        # E.g. read_size == 16, i.e. 2 byte variables are used to store the
        # result of reading.
        # Reading result is different from endianness (2 consecutive readings).
        # Big-endian (high byte on the left):
        # var0_16 = [[ 0 ][ 1 ]]
        # var1_16 = [[ 2 ][ 3 ]]
        # Little-endian (high byte on the left):
        # var0_16 = [[ 1 ][ 0 ]]
        # var1_16 = [[ 3 ][ 2 ]]
        # Instruction description declares the value after reading.
        # XXX: тогда причём тут порядок байт? Если инструкция 4-х байтовая, а
        #      размер слова 2, то я знаю, что сначала будет считано слово с
        #      меньшим адресом. Т.к. порядок байт важен только внутри слова.
        #      Т.е. я и буду описывать поля сначала для первого слова, потом
        #      для второго и т.д.
        #
        # E.g. desired field has an offset == 18 and length == 5.
        # With such an offset it is in the `var1_16` variable
        # (var_offset == 16 and var_length == 16).
        #  var0_16           var1_16
        #  111111            111111
        #  5432109876543210  5432109876543210  bit indices in variables
        # XXX: нужно сопоставить с битами из описания.
        # [                ][                ]
        # [---------------->[                  var_offset == 16
        # [--------------------->(             offset == 18
        #                   [--->(             local_offset == 2
        #                        (field)       length == 5
        #                              )---->] shift_val (desired offset)
        #
        # XXX: на рисунках (field) не попадает в нужные биты, как и многое
        # другое.

        # `shift_val` calculation is performed in steps:
        #                   [<---------------] var_length == 16
        #                   [--->(             local_offset == 2
        #                        (---->)       length == 5
        #                              )---->] shift_val == 9
        #
        # Reads can be optimized.
        # E.g. instead of two 16bit reads, one 32bit read.
        # Big-endian (high byte on the left):
        # var0_32 = [[ 0 ][ 1 ][ 2 ][ 3 ]] = [[var0_16][var1_16]]
        # Little-endian (high byte on the left):
        # var0_32 = [[ 3 ][ 2 ][ 1 ][ 0 ]] = [[var1_16][var0_16]]
        # XXX: вот тут уже можно догадаться, как порядок байт влияет на
        #      описание инструкций. Нужно ясно объяснить, что слова описаний,
        #      попавшие на подобные длинные чтения, нужно интерпретировать
        #      в другом порядке.
        #
        # For big-endian calculation is performed same:
        #  var0_32
        #  var0_16         var1_16
        #  3322222222221111111111
        #  10987654321098765432109876543210  bit indices in variable
        # [                                ]
        # [                                  var_offset == 0
        # [------------------->(             offset == 18
        # [------------------->(             local_offset == 18
        #                      (field)       length == 5
        #                            )---->] shift_val (desired offset)
        #
        # [<-------------------------------] var_length == 32
        # [------------------->(             local_offset == 18
        #                      (---->)       length == 5
        #                            )---->] shift_val == 9
        #
        # But for little-endian the positions of the subvariables are reversed.
        # Therefore, the local offset must be recalculated:
        # XXX: внизу формуля другая и не приводится к этой очевидными способами
        # XXX: ваще не понятно, откуда взялась ни та, ни другая. Нужна схема
        #      для тупых
        # XXX: очень интересемслучай, когда поле пересекает границу слов
        # XXX: кстати, схему с текстом можно нарисовать в векторной форме,
        #      а в коммент вставить имя файла
        # new_local_offset = local_offset % read_size + read_size * (
        #     var_length // read_size - local_offset // read_size - 1
        # )
        # new_local_offset == 2
        #
        #  var0_32
        #  var1_16         var0_16
        #  3322222222221111111111
        #  10987654321098765432109876543210  bit indices in variable
        # [                                ]
        # [<-------------------------------] var_length == 32
        # [-->(                              new_local_offset == 2
        #     (---->)                        length == 5
        #           )--------------------->] shift_val == 25

        local_offset = offset - var_offset

        # We must account the endianness of CPU if the variable length is
        # larger than the read size.
        if self.target_bigendian:
            shift_val = var_length - length - local_offset
        else:
            swap_size = self.read_size
            shift_val = (swap_size + local_offset -
                2 * (local_offset % swap_size) - length
            )

        return shift_val

    def get_operand_part(self, oper, vars_desc):
        # XXX: what this loop looking for? (a comment)
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

        for name, parts in instruction.iter_operand_parts():
            shift = 0
            rval = None
            # TODO: this is a coding style feature,
            #       generalize it inside source.function.tree
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
                # XXX: NotImplementedError? Суть проблемы в том, что мы не
                #      поддерживаем (не хотим пока) более Int128 и т.д....
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

    def gen_subtree_code(self, gen_node, instr_node, vars_desc = []):
        # XXX: avoid using opc[...]
        opc = instr_node.opcode
        ins = instr_node.instruction
        reads_desc = instr_node.reads_desc

        if ins is None:
            # XXX: этот код дублируется
            new_vars = self.read_fields(gen_node, reads_desc)
            if new_vars is not None:
                vars_desc = vars_desc + new_vars
                self.vars.update(v[0] for v in new_vars)

            # XXX: клммент, что ищет этот цикл
            for var, var_off, var_len in reversed(vars_desc):
                if (    var_off <= opc[0]
                    and opc[0] + opc[1] <= var_off + var_len
                ):
                    break

            shift_val = self.calc_shift_val(var_off, var_len, opc[0], opc[1])

            cases = []
            default_sc = None
            for key, node in instr_node.subtree.items():
                # XXX: `key` is actually `opcode`
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

                self.gen_subtree_code(sc, node, vars_desc = vars_desc)

            if default_sc is not None:
                cases.append(default_sc)
            else:
                # If subtree hasn't `default` key it means subtree hasn't
                # instr_node with `default` opc and we must exit cpu loop in
                # `default` branch.
                # XXX: did we met an unknown instruction here?
                cases.append(self.default_switch_case)

            # XXX: opc_mask = ((1 << opc[1]) - 1) << shift_val  ?
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


# glue functions to get rid of direct body tree filling in cpu creation code
# XXX: теперь мы - липкие бандиты (давай без клея в комментах, да)
#      functions filling/generating CPU & TCG front-end implementation

def fill_bfd_getb64_body(function):
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

def fill_class_by_name_body(cputype, function):
    function.body = body = BodyTree()

    oc = Pointer(Type["ObjectClass"])("oc")
    cpu_model = function.args[0]
    null = MCall("NULL")

    if get_vp("cpu_model null check"):
        body(
            Declare(oc),
            NewLine(),
            BranchIf(OpEq(cpu_model, null))(Return(null)),
            OpAssign(oc, Call("object_class_by_name", cpu_model))
        )
    else:
        body(
            Declare(
                OpDeclareAssign(
                    oc,
                    Call("object_class_by_name", cpu_model)
                )
            )
        )

    body(
        BranchIf(
            OpLogAnd(
                OpNEq(oc, null),
                OpLogOr(
                    OpEq(
                        Call(
                            "object_class_dynamic_cast",
                            oc,
                            MCall(cputype.qtn.type_macro)
                        ),
                        null
                    ),
                    Call("object_class_is_abstract", oc)
                )
            )
        )(Return(null)),
        Return(oc)
    )

def fill_class_init_body(cputype, function, num_core_regs, vmstate):
    function.body = body = BodyTree()

    oc = function.args[0]
    dc = Pointer(Type["DeviceClass"])("dc")
    cc = Pointer(Type["CPUClass"])("cc")
    mcc = Pointer(Type[cputype.struct_class_name])("mcc")

    fn_name = cputype.gen_func_name

    body(
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
                MCall(cputype.class_macro, oc)
            )
        ),
        NewLine()
    )

    if get_vp("device_class_set_parent_realize exists"):
        body(
            Call(
                "device_class_set_parent_realize",
                dc,
                Type[fn_name("realizefn")],
                OpAddr(OpSDeref(mcc, "parent_realize")),
            )
        )
    else:
        body(
            OpAssign(
                OpSDeref(mcc, "parent_realize"),
                OpSDeref(dc, "realize")
            ),
            OpAssign(
                OpSDeref(dc, "realize"),
                Type[fn_name("realizefn")]
            )
        )

    body(
        OpAssign(
            OpSDeref(mcc, "parent_reset"),
            OpSDeref(cc, "reset")
        )
    )
    body(*[
        OpAssign(
            OpSDeref(cc, name),
            Type[fn_name(name)]
        ) for name in ["reset", "has_work", "do_interrupt", "set_pc",
            "dump_state", "disas_set_info", "class_by_name"
        ]
    ])
    body(
        OpAssign(
            OpSDeref(cc, "vmsd"),
            OpAddr(vmstate)
        ),
        OpAssign(
            OpSDeref(cc, "gdb_num_core_regs"),
            num_core_regs
        )
    )
    body(*[
        OpAssign(
            OpSDeref(cc, name),
            Type[fn_name(name)]
        ) for name in ["gdb_read_register", "gdb_write_register",
            "get_phys_page_debug"
        ]
    ])

    if get_vp("Generic call to tcg_initialize"):
        body(
            OpAssign(
                OpSDeref(cc, "tcg_initialize"),
                Type[cputype.tcg_init_name]
            )
        )

    if get_vp("CPUClass has tlb_fill field"):
        body(
            OpAssign(
                OpSDeref(cc, "tlb_fill"),
                Type[cputype.gen_func_name("tlb_fill")]
            )
        )

def fill_cpu_get_tb_cpu_state_body(function, pc_register):
    function.body = BodyTree()(
        OpAssign(
            OpDeref(function.args[1]),
            OpSDeref(function.args[0], pc_register)
        ),
        OpAssign(OpDeref(function.args[2]), 0),
        OpAssign(OpDeref(function.args[3]), 0)
    )

def fill_cpu_init_body(cputype, function):
    function.body = BodyTree()(
        Return(
            MCall(
                cputype.qtn.for_macros,
                Call("cpu_generic_init", MCall(cputype.qtn.type_macro),
                    function.args[0]
                )
            )
        )
    )

def fill_cpu_mmu_index_body(function):
    function.body = BodyTree()(Return(0))

def fill_cpuclass_tlb_fill_body(function):
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

def fill_decode_opc_body(cputype, function, cpu_env):
    function.body = body = BodyTree()

    result = Type["int"]("result")
    body(Declare(OpDeclareAssign(result, 0)))

    ctx = function.args[1]
    ctx_pc = OpSDeref(ctx, "pc")
    set_pc_ref = {Type["set_pc"]}

    h = cputype.gen_files["translate.inc.c"]

    def gen_field_read(node, val, offset, length):
        offset //= BYTE_SIZE
        length //= BYTE_SIZE
        env = OpAddr(OpSDeref(function.args[0], "env"))

        # XXX: it can be cached in kwargs
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

    # XXX: то node, то gen_node
    def decode_opc_epilogue(gen_node, instr_node, operands, text):
        instr_args = [ Pointer(Type["DisasContext"])("ctx") ]
        existing_names = defaultdict(lambda : count(0))
        for o in operands:
            v = copy(o)
            parts = o.name.split('_')
            if len(parts) > 1:
                # XXX: [see chat about this]
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

        func = Function(
            name = instr_node.instruction.name,
            body = BodyTree()(
                Comment(text),
                *instr_node.instruction.semantics()
            ),
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

    default_switch_case_nodes = [
        Call("set_pc", ctx_pc),
        Call("gen_helper_illegal", cpu_env),
        OpAssign(
            OpSDeref(ctx, "bstate"),
            Type["BS_EXCP"]
        )
    ]

    ParseTreeCodeBuilder(cputype, body, gen_field_read, decode_opc_epilogue,
        result, default_switch_case_nodes
    )

    body(Return(result))

def fill_disas_set_info_body(cputype, function):
    function.body = BodyTree()(
        OpAssign(
            OpSDeref(function.args[1], "mach"),
            getattr(Type["bfd_architecture"], cputype.bfd_arch_name)
        ),
        OpAssign(
            OpSDeref(function.args[1], "print_insn"),
            Type[cputype.print_insn_name]
        )
    )

def fill_disas_write_helper_body(function):
    function.body = BodyTree()(Return(0))

def fill_dump_state_body(cputype, function, reg_vars):
    function.body = body = BodyTree()

    cpu = Pointer(Type[cputype.struct_instance_name])("cpu")
    env = Pointer(Type[cputype.struct_name])("env")

    out_file = function.args[1]
    if get_vp("dump_state has cpu_fprintf argument"):
        fprintf_func = function.args[2]
    else:
        fprintf_func = Type["qemu_fprintf"]
    i = Type["int"]("i")

    body(
        Declare(
            OpDeclareAssign(
                cpu,
                MCall(cputype.qtn.for_macros, function.args[0])
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
            body(
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
            body(
                Call(
                    fprintf_func,
                    out_file,
                    r.name + "=0x%08x\\n",
                    OpSDeref(env, r.name)
                )
            )

def fill_env_get_cpu_body(cputype, function):
    function.body = BodyTree()(
        Return(
            MCall(
                "container_of",
                function.args[0],
                Type[cputype.struct_instance_name],
                Node("env")
            )
        )
    )

def fill_gdb_rw_register_body(cputype, function, comment):
    cpu = Pointer(Type[cputype.struct_instance_name])("cpu")
    cc = Pointer(Type["CPUClass"])("cc")
    env = Pointer(Type[cputype.struct_name])("env")

    ret_0 = Return(0)

    function.body = BodyTree()(
        Comment(comment),
        Declare(
            OpDeclareAssign(
                cpu,
                MCall(cputype.qtn.for_macros, function.args[0])
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

def fill_gen_intermediate_code_body(cputype, function, cpu_env):
    function.body = body = BodyTree()

    if get_vp("gen_intermediate_code arg1 is generic"):
        env = Pointer(Type[cputype.struct_name])("env")
        body(
            Declare(
                OpDeclareAssign(
                    env,
                    OpSDeref(function.args[0], "env_ptr")
                )
            )
        )
    else:
        env = function.args[0]

    cpu = Pointer(Type[cputype.struct_instance_name])("cpu")
    ctx = Type["DisasContext"]("ctx")
    ctx_pc = OpSDeref(ctx, "pc")
    ctx_tb = OpSDeref(ctx, "tb")
    set_pc = Call("set_pc", ctx_pc)
    gen_helper_debug = Call("gen_helper_debug", cpu_env)
    ctx_bstate = OpSDeref(ctx, "bstate")
    tb = function.args[1]

    body(
        Declare(
            OpDeclareAssign(
                cpu,
                Call(
                    (
                        "env_archcpu" if get_vp("env_archcpu exists") else
                        cputype.env_get_cpu_name
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
        body(
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

    body(
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
        body(
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

    body(
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
                    # Note, there may be a grammatical error with
                    # "in order to for it" but to preserve the identity with
                    # the Qemu-master branch the comment is written as is.
                    Comment("The address covered by the breakpoint must be"
                        " included in [tb->pc, tb->pc + tb->size) in order"
                        " to for it to be properly cleared -- thus we"
                        " increment the PC here so that the logic setting"
                        " tb->size below does the right thing."
                    ),
                    OpCombAssign(
                        ctx_pc,
# See https://lists.gnu.org/archive/html/qemu-devel/2015-10/msg03668.html
                        int(cputype.min_instr_size / 8),
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

def fill_get_phys_page_debug_body(function):
    function.body = BodyTree()(Return(function.args[1]))

def fill_handle_mmu_fault_body(function):
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

def fill_has_work_body(function):
    function.body = BodyTree()(
        Return(
            OpAnd(
                OpSDeref(function.args[0], "interrupt_request"),
                MCall("CPU_INTERRUPT_HARD")
            )
        )
    )

def fill_helper_debug_body(function):
    function.body = BodyTree()(
        Call(
            "raise_exception",
            function.args[0],
            MCall("EXCP_DEBUG")
        )
    )

def fill_helper_illegal_body(function):
    function.body = BodyTree()(
        Call(
            "raise_exception",
            function.args[0],
            Type["EXCP_ILLEGAL"]
        )
    )

def fill_initfn_body(cputype, function):
    function.body = body = BodyTree()

    cpu = Pointer(Type[cputype.struct_instance_name])("cpu")
    cs = Pointer(Type["CPUState"])("cs")
    for_macros = cputype.qtn.for_macros

    if get_vp("cpu_set_cpustate_pointers exists"):
        body(
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(for_macros, function.args[0])
                )
            ),
            NewLine(),
            Call(
                "cpu_set_cpustate_pointers",
                cpu
            )
        )
    elif get_vp("Generic call to tcg_initialize"):
        body(
            Declare(
                OpDeclareAssign(
                    cs,
                    MCall("CPU", function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(for_macros, function.args[0])
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

        body(
            Declare(
                OpDeclareAssign(
                    cs,
                    MCall("CPU", function.args[0])
                )
            ),
            Declare(
                OpDeclareAssign(
                    cpu,
                    MCall(for_macros, function.args[0])
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
                Call(cputype.tcg_init_name)
            )
        )

def fill_print_insn_body(cputype, function):
    function.body = body = BodyTree()

    status = Type["int"]("status")
    buffer_ = Type["bfd_byte"]("buffer", array_size = 6)
    length = Type["int"]("length")
    stream = Pointer(Type["void"])("stream")
    fpr = Type["fprintf_function"]("fpr")

    body(
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
                    'b' if cputype.target_bigendian else 'l',
                    length
                ),
                buffer_
            )
            # shift result due to implementation of bfd_getb16
            if cputype.target_bigendian and length == 16:
                bfd_get = OpRShift(bfd_get, 16)

        node(Declare(OpDeclareAssign(val, bfd_get)))

    def print_ins_epilogue(gen_node, instr_node, operands, _):
        operands_dict = { o.name: o for o in operands }

        format_line = ''
        call_args = []
        name_to_format = cputype.name_to_format
        # TODO: `disas_format`'s format is not trivial, add a doc to
        #       `Instruction` class
        # XXX: use re.compile and place it near `Instruction` as a hint to a
        #      user about `disas_format`'s format
        for m in finditer("<(.+?)>|([^<>]+)",
            instr_node.instruction.disas_format
        ):
            try:
                gr = m.group(1)
                fmt, adapter = name_to_format[gr]
                variables = []
                for i in gr.split(','):
                    name = i.strip().split('$')[0]
                    variables.append(operands_dict.get(name, CINT(name)))

                if fmt is None:
                    if format_line:
                        gen_node(
                            Call(fpr, stream, format_line, *call_args)
                        )
                        format_line = ''
                        call_args = []
                    gen_node(Call(adapter, fpr, stream, *variables))
                    continue
                else:
                    format_line += fmt

                if adapter is None:
                    for var in variables:
                        if isinstance(var, Variable):
                            call_args.append(OpCast("unsigned", var))
                        else:
                            call_args.append(var)
                else:
                    call_args.append(Call(adapter, *variables))
            # XXX: too many things may raise `KeyError`. Move most of it to
            #      `else` block
            except KeyError:
                format_line += m.group(0)

        if format_line:
            gen_node(Call(fpr, stream, format_line, *call_args))

    default_switch_case_nodes = [
        Call("fprintf", MCall("stderr"), "Unknown instruction\\n"),
        Call("abort")
    ]

    ParseTreeCodeBuilder(cputype, body, gen_disas_opcode_read,
        print_ins_epilogue, length, default_switch_case_nodes,
        add_break = False
    )

    body(
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

def fill_raise_exception_body(cputype, function):
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
                        Call(cputype.env_get_cpu_name, function.args[0])
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

def fill_realizefn_body(cputype, function):
    cs = Pointer(Type["CPUState"])("cs")
    cc = Pointer(Type[cputype.struct_class_name])("cc")
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
                MCall(cputype.get_class_macro, function.args[0])
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

def fill_reset_body(cputype, function):
    function.body = body = BodyTree()

    cpu = Pointer(Type[cputype.struct_instance_name])("cpu")
    cc = Pointer(Type[cputype.struct_class_name])("cc")
    env = Pointer(Type[cputype.struct_name])("env")

    body(
        Declare(
            OpDeclareAssign(
                cpu,
                MCall(cputype.qtn.for_macros, function.args[0])
            )
        ),
        Declare(
            OpDeclareAssign(
                cc,
                MCall(cputype.get_class_macro, cpu)
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
        body(
            Call(
                "memset",
                env,
                0,
                MCall(
                    "offsetof",
                    Type[cputype.struct_name],
                    Node("end_reset_fields")
                )
            ),
            OpAssign(
                OpSDeref(env, cputype.pc_register),
                0
            )
        )
    else:
        body(
            Call(
                "memset",
                env,
                0,
                OpSizeOf(
                    Type[cputype.struct_name]
                )
            ),
            OpAssign(
                OpSDeref(env, cputype.pc_register),
                0
            ),
            Call(
                "tlb_flush",
                function.args[0],
                1
            )
        )

def fill_restore_state_to_opc_body(cputype, function):
    function.body = BodyTree()(
        OpAssign(
            OpSDeref(function.args[0], cputype.pc_register),
            OpIndex(function.args[2], 0)
        )
    )

def fill_set_pc_body(cputype, function):
    cpu = Pointer(Type[cputype.struct_instance_name])("cpu")

    function.body = BodyTree()(
        Declare(
            OpDeclareAssign(
                cpu,
                MCall(cputype.qtn.for_macros, function.args[0])
            )
        ),
        NewLine(),
        OpAssign(
            OpSDeref(OpSDeref(cpu, "env"), cputype.pc_register),
            function.args[1]
        )
    )

def fill_set_pc_inc_body(function, pc):
    function.body = BodyTree()(OpAssign(pc, function.args[0]))

def fill_tcg_init_body(cputype, function, reg_vars, cpu_env):
    function.body = body = BodyTree()

    i = Type["int"]("i")

    if get_vp("Generic call to tcg_initialize"):
        body(
            Declare(i),
            NewLine()
        )
    else:
        done_init = Type["int"]("done_init", static = True)
        body(
            Declare(done_init),
            Declare(i),
            NewLine(),
            BranchIf(done_init)(
                Return()
            )
        )

    if get_vp("Init cpu_env in arch"):
        body(
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

    cpu_arch_state = Type[cputype.struct_name]
    for r, var, names_array in reg_vars:
        if r.len:
            parent_node = LoopFor(
                OpAssign(i, 0), OpLess(i, r.len), OpPreInc(i)
            )
            body(parent_node)
            v = OpIndex(var, i)
            state_field = OpIndex(Node(r.name), i)
            string_name = OpIndex(names_array, i)
        else:
            parent_node = body
            v = var
            state_field = Node(r.name)
            string_name = CSTR(r.name)

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
        body(OpAssign(done_init, 1))

def fill_tlb_fill_body(cputype, function):
    function.body = body = BodyTree()

    fn_name = cputype.gen_func_name

    if get_vp("CPUClass has tlb_fill field"):
        body(
            Call(
                fn_name("tlb_fill"),
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

        body(
            Declare(
                OpDeclareAssign(
                    ret,
                    Call(
                        fn_name("handle_mmu_fault"),
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
