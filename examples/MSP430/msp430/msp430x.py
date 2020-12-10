from source import *
from qemu import *

from functools import (
    wraps,
)

# TODO: source.function.tree.Node:
#     * / % > < >= <= == != : to corresponding operators
#     += -= *= /= %= <<= >>= &= ^= |= : to corresponding CombAssign operators


# shortcuts
c = Opcode
o = Operand


# cache some types
tcg = Type["tcg"]
MemOp = Type[get_vp("memop")]
MO_UB = MemOp.MO_UB
MO_UW = MemOp.MO_UW
MO_UL = MemOp.MO_UL
MO_TE = MemOp.MO_TE
int_ = Type["int"]
uint32_t = Type["uint32_t"]
uint64_t = Type["uint64_t"]


# Temporal storage for instructions descriptions during generation.
instructions = list()

# Do generate MSP430X (eXtended) instructions descriptions?
with_ext = True


def i(name, *a, **kw):
    instr = Instruction(name, *a, **kw)
    instructions.append(instr)
    return instr


class FI(object):

    def __init__(self, opcode,
        changes_dst = True,
        reads_dst = True,
        # Flags mark usage by semantics code
        msb_used = True,
        mask_used = True,
        carry_used = True
    ):
        self.opcode = opcode
        self.changes_dst = changes_dst
        self.reads_dst = reads_dst
        self.msb_used = msb_used
        self.mask_used = mask_used
        self.carry_used = carry_used

    def __call__(self, sem):
        append_FI(self.opcode, sem.__name__.lower(), sem, self.changes_dst,
            self.reads_dst, self.msb_used, self.mask_used, self.carry_used
        )
        return sem


class FII(object):

    def __init__(self, opcode,
        changes_dst = True,
        has_ext = True,
        sub_sp = False,
        save_pc = False,
        # Flags mark usage by semantics code
        msb_used = True,
        mask_used = True,
        carry_used = True
    ):
        self.opcode = opcode
        self.changes_dst = changes_dst
        self.has_ext = has_ext
        self.sub_sp = sub_sp # Note, True for PUSH and CALL only
        self.save_pc = save_pc # Note, True for CALL only
        self.msb_used = msb_used
        self.mask_used = mask_used
        self.carry_used = carry_used

    def __call__(self, sem):
        append_FII(self.opcode, sem.__name__.lower(), self.has_ext, sem,
            self.changes_dst, self.sub_sp, self.save_pc, self.msb_used,
            self.mask_used, self.carry_used
        )
        return sem


class J(object):

    def __init__(self, opcode):
        self.opcode = opcode

    def __call__(self, sem):
        append_J(self.opcode, sem.__name__.lower(), sem)
        return sem


class R(object):

    def __init__(self, opcode):
        self.opcode = opcode

    def __call__(self, sem):
        append_R(self.opcode, sem.__name__.lower(), sem)
        return sem


def append_FI(opcode, base_name, semantics, changes_dst, reads_dst, msb_used,
    mask_used, carry_used, **kw
):
    "Double-Operand Instruction, Format I"

    # Addressing modes
    # # Source addressing modes, As
    # 00 - register
    # 01 - indexed (X(Rn)), symbolic (X(PC)), absolute (X(SR)) (extra word)
    # 10 - indirect register @Rn
    # 11 - indirect autoincrement @Rn+
    #    - immediate @PC+, #N (extra word) - looks like PC is incremented
    #      before extra destination (if Ad) word is read, so the destination
    #      word location depends on Rn == PC (0) when As == 11b
    # # Destination addressing modes, Ad
    # 0 - register
    # 1 - indexed X(Rn), symbolic X(PC), absolute X(SR) (extra word)

    for ext in ((True, False) if with_ext else (False,)):
        # common for all instructions
        if ext:
            name = base_name + "x"
            # ext_word is defined depending on instruction variant
            fmt_bwa = ".<bw, al>"
        else:
            name = base_name
            ext_word = []
            fmt_bwa = ".<bw>" # al field exists in extension word only

        for ad in (
            0, # dst: register
            1 # dst: indexed/symbolic/absolute (extra word)
        ):
            if ad:
                dst_offset = [o(16, "doff")]
                dst_suffix = "_idx"
                dst_fmt = "<dst, doff>"
                # only used for Non-Register Mode Extension Word
                ext_word_dst_suffix = [o(4, "doff", 1)]
            else:
                dst_offset = []
                dst_suffix = "_reg"
                dst_fmt = "<dst>"
                ext_word_dst_suffix = [c(4, 0)]

            NAME = name.upper()
            common_format = NAME + fmt_bwa + "\\t "

            # src: immediate
            if ext:
                # Non-Register Mode Extension Word
                ext_word = [
                    c(5, 0b00011),
                    o(4, "soff", 1),
                    o(1, "al"),
                    c(2, 0)
                ] + ext_word_dst_suffix

            kw["disas_format"] = common_format + "#<soff>, " + dst_fmt

            fields = ext_word + [
                c(4, opcode),
                c(4, 0), # src is PC
                c(1, ad),
                o(1, "bw"), # B/W
                c(2, 3), # As == 11b, immediate as src == 0
                o(4, "dst"),
                o(16, "soff")
            ] + dst_offset

            kw["priority"] = 1

            @i(name + "_imm" + dst_suffix, *fields, **kw)
            @wraps(semantics)
            @flat_list
            def src_imm_sem(f, s, ad = ad, ext = ext):
                src_val = tcg("src_val")
                tcg_mem_size = MemOp("size")
                mem_addr = None

                bits = []
                yield gen_define_size_bits(f, s, ext, bits, msb_used,
                    mask_used or changes_dst, # because `mask` used
                    carry_used
                )

                if reads_dst or changes_dst:
                    yield gen_set_mem_size(f, s, ad, ext, tcg_mem_size)
                    if ad:
                        mem_addr = tcg("mem_addr")
                        yield Call(
                            "get_dst_mem_addr",
                            mem_addr,
                            f["ctx"],
                            f["dst"],
                            f["doff"],
                            6 if ext else 4
                        )

                if reads_dst:
                    dst_val = tcg("dst_val")
                    yield gen_get_dst_code(f, s, ext, ad, dst_val,
                        tcg_mem_size, mem_addr, 6 if ext else 4
                    )
                else:
                    dst_val = None

                yield OpAssign(src_val, f["soff"])

                res = tcg("res")
                yield semantics(f, s, src_val, dst_val, res, *bits)

                if changes_dst:
                    yield OpCombAssign(res, bits[1], "&") # mask
                    yield gen_set_dst_code(f, s, ad, res, tcg_mem_size,
                        mem_addr
                    )

            # src: src == R3 (CG2)
            # There is no soff at end of the instruction
            kw["disas_format"] = common_format + "#<as>, " + dst_fmt

            fields = ext_word + [
                c(4, opcode),
                c(4, 3), # src == 3
                c(1, ad),
                o(1, "bw"), # B/W
                o(2, "as"),
                o(4, "dst")
            ] + dst_offset

            kw["priority"] = 2

            @i(name + "_cg2" + dst_suffix, *fields, **kw)
            @wraps(semantics)
            @flat_list
            def src_cg2_sem(f, s, ad = ad, ext = ext):
                src_val = tcg("src_val")
                tcg_mem_size = MemOp("size")
                mem_addr = None

                bits = []
                yield gen_define_size_bits(f, s, ext, bits, msb_used,
                    True, # `mask_used` is ignored because the `gen_set_cg2`
                    # uses `mask`
                    carry_used
                )

                yield gen_set_cg2(f, s, src_val, f["as"], *bits)

                if reads_dst or changes_dst:
                    yield gen_set_mem_size(f, s, ad, ext, tcg_mem_size)
                    if ad:
                        mem_addr = tcg("mem_addr")
                        yield Call(
                            "get_dst_mem_addr",
                            mem_addr,
                            f["ctx"],
                            f["dst"],
                            f["doff"],
                            4 if ext else 2
                        )

                if reads_dst:
                    dst_val = tcg("dst_val")
                    yield gen_get_dst_code(f, s, ext, ad, dst_val,
                        tcg_mem_size, mem_addr, 4 if ext else 2
                    )
                else:
                    dst_val = None

                res = tcg("res")
                yield semantics(f, s, src_val, dst_val, res, *bits)

                if changes_dst:
                    yield OpCombAssign(res, bits[1], "&") # mask
                    yield gen_set_dst_code(f, s, ad, res, tcg_mem_size,
                        mem_addr
                    )

            # src: indexed/symbolic/absolute
            # if ext: ext_word is same as previously
            kw["disas_format"] = common_format + "<src, soff>, " + dst_fmt

            fields = ext_word + [
                c(4, opcode),
                o(4, "src"), # src is any
                c(1, ad),
                o(1, "bw"), # B/W
                c(2, 1), # As == 01b, indexed/symbolic/absolute
                o(4, "dst"),
                o(16, "soff")
            ] + dst_offset

            kw["priority"] = 1

            @i(name + "_idx" + dst_suffix, *fields, **kw)
            @wraps(semantics)
            @flat_list
            def src_idx_sem(f, s, ad = ad, ext = ext):
                src = f["src"]
                soff = f["soff"]
                src_val = tcg("src_val")
                tcg_mem_size = MemOp("size")

                bits = []
                yield gen_define_size_bits(f, s, ext, bits, msb_used,
                    mask_used or changes_dst, # because `mask` used
                    carry_used
                )

                # tcg_mem_size is required because of src indexed mode
                yield gen_set_mem_size(f, s, True, ext, tcg_mem_size)
                yield gen_get_operand_idx_code(f, s, ext, src, soff, src_val,
                    tcg_mem_size
                )

                if (reads_dst or changes_dst) and ad:
                    mem_addr = tcg("mem_addr")
                    yield Call(
                        "get_dst_mem_addr",
                        mem_addr,
                        f["ctx"],
                        f["dst"],
                        f["doff"],
                        6 if ext else 4
                    )
                else:
                    mem_addr = None

                if reads_dst:
                    dst_val = tcg("dst_val")
                    yield gen_get_dst_code(f, s, ext, ad, dst_val,
                        tcg_mem_size, mem_addr, 6 if ext else 4
                    )
                else:
                    dst_val = None

                res = tcg("res")
                yield semantics(f, s, src_val, dst_val, res, *bits)

                if changes_dst:
                    yield OpCombAssign(res, bits[1], "&") # mask
                    yield gen_set_dst_code(f, s, ad, res, tcg_mem_size,
                        mem_addr
                    )

            # src: (indirect) register (autoincrement)
            kw["disas_format"] = common_format + "<src, as>, " + dst_fmt

            if ext:
                if not ad:
                    # Register Mode Extension Word
                    # Note, now used not only for Register/Register mode, but
                    # for (Indirect) Register (Autoincrement)/Register mode.
                    ext_word = [
                        c(7, 0b0001100),
                        o(1, "zc"),
                        o(1, "rep"),
                        o(1, "al"),
                        c(2, 0b00),
                        o(4, "reg_or_n") # depends on rep
                    ]

                    kw["disas_format"] = "<rep, reg_or_n>" + kw["disas_format"]
                # else: ext_word is same as previously

            fields = ext_word + [
                c(4, opcode),
                o(4, "src"), # src is not PC
                c(1, ad),
                o(1, "bw"), # B/W
                o(2, "as"), # (As == 00b) or (As == 10b) or (As == 11b and src != 0)
                o(4, "dst")
            ] + dst_offset

            kw["priority"] = 0

            @i(name + "_reg" + dst_suffix, *fields, **kw)
            @wraps(semantics)
            @flat_list
            def src_reg_sem(f, s, ad = ad, ext = ext):
                _as = f["as"]
                src = f["src"]
                src_val = tcg("src_val")
                tcg_mem_size = MemOp("size")
                mem_addr = None

                # TODO: repetition mode (ext)
                # TODO: Zero carry (ext)

                bits = []
                yield gen_define_size_bits(f, s, ext, bits, msb_used,
                    mask_used or changes_dst, # because `mask` used
                    carry_used
                )

                if ad:
                    yield gen_set_mem_size(f, s, True, ext, tcg_mem_size)
                    if reads_dst or changes_dst:
                        mem_addr = tcg("mem_addr")
                        yield Call(
                            "get_dst_mem_addr",
                            mem_addr,
                            f["ctx"],
                            f["dst"],
                            f["doff"],
                            4 if ext else 2
                        )
                else:
                    yield BranchIf(OpLE(2, _as))(
                        gen_set_mem_size(f, s, True, ext, tcg_mem_size)
                    )

                yield gen_get_oper_reg_code(f, s, ext, _as, src, src_val,
                    tcg_mem_size, 4 if ext else 2, ad, False
                )
                if reads_dst:
                    dst_val = tcg("dst_val")
                    yield gen_get_dst_code(f, s, ext, ad, dst_val,
                        tcg_mem_size, mem_addr, 4 if ext else 2
                    )
                else:
                    dst_val = None

                res = tcg("res")
                yield semantics(f, s, src_val, dst_val, res, *bits)

                if changes_dst:
                    yield OpCombAssign(res, bits[1], "&") # mask
                    yield gen_set_dst_code(f, s, ad, res, tcg_mem_size,
                        mem_addr
                    )


def append_FII(opcode, base_name, has_ext, semantics, changes_dst, sub_sp,
    save_pc, msb_used, mask_used, carry_used,
    **kw
):
    "Single-Operand Instruction, Format II"

    # There is no explicit confirmation found in the ISA manual but this looks
    # like Ad of format 2 instructions has same semantics as As of format 1.

    for ext in [False] + ([True] if (has_ext and with_ext) else []):
        if ext:
            name = base_name + "x"
            # ext_word is defined depending on instruction variant
            fmt_bwa = ".<bw, al>"
        else:
            name = base_name
            ext_word = []
            fmt_bwa = ".<bw>"

        NAME = name.upper()

        common_format = NAME + fmt_bwa + "\\t "

        # dst: immediate
        if ext:
            ext_word = [
                c(9, 0b000110000),
                o(1, "al"),
                c(2, 0),
                o(4, "doff", 1)
            ]

        fields = ext_word + [
            c(9, opcode),
            o(1, "bw"), # B/W
            c(2, 3), # Ad == 11b, immediate as Rdst == 0
            c(4, 0), # Rdst is PC
            o(16, "doff")
        ]

        kw["disas_format"] = common_format + "#<doff>"

        kw["priority"] = 0

        @i(name + "_imm", *fields, **kw)
        @wraps(semantics)
        @flat_list
        def dst_imm_sem(f, s, ext = ext):
            res = tcg("res")

            bits = []
            yield gen_define_size_bits(f, s, ext, bits,
                msb_used or (sub_sp and ext), # because `gen_sub_sp` uses `msb`
                mask_used, carry_used
            )

            if sub_sp:
                yield gen_sub_sp(f, s, ext, *bits)

            if save_pc:
                yield gen_save_pc(f, s, 6 if ext else 4)

            dst_val = tcg("dst_val")
            yield OpAssign(dst_val, f["doff"])

            yield semantics(f, s, dst_val, res, 6 if ext else 4, ext, *bits)

        # dst: dst==3 => CG2
        # if ext: is ext_word same as previously? There is no doff

        fields = ext_word + [
            c(9, opcode),
            o(1, "bw"), # B/W
            o(2, "ad"),
            c(4, 3) # Rdst is R3 (CG2)
        ]

        kw["disas_format"] = common_format + "#<ad>"

        kw["priority"] = 1

        @i(name + "_cg2", *fields, **kw)
        @wraps(semantics)
        @flat_list
        def dst_cg2_sem(f, s, ext = ext):
            dst_val = tcg("dst_val")

            bits = []
            yield gen_define_size_bits(f, s, ext, bits,
                msb_used or (sub_sp and ext), # because `gen_sub_sp` uses `msb`
                True, # `mask_used` is ignored because the `gen_set_cg2` uses
                # `mask`
                carry_used
            )

            if sub_sp:
                yield gen_sub_sp(f, s, ext, *bits)

            if save_pc:
                yield gen_save_pc(f, s, 4 if ext else 2)

            yield gen_set_cg2(f, s, dst_val, f["ad"], *bits)

            res = tcg("res")
            yield semantics(f, s, dst_val, res, 4 if ext else 2, ext, *bits)

            # it can't change dst

        # dst: indexed/symbolic/absolute
        # if ext: ext_word is same as previously

        fields = ext_word + [
            c(9, opcode),
            o(1, "bw"), # B/W
            c(2, 1), # Ad == 01b, indexed/symbolic/absolute
            o(4, "dst"), # Rdst
            o(16, "doff")
        ]

        kw["disas_format"] = common_format + "<dst, doff>"

        kw["priority"] = 0

        @i(name + "_ind", *fields, **kw)
        @wraps(semantics)
        @flat_list
        def dst_idx_sem(f, s, ext = ext):
            dst = f["dst"]
            doff = f["doff"]
            dst_val = tcg("dst_val")
            tcg_mem_size = MemOp("size")
            mem_addr = tcg("mem_addr")

            bits = []
            yield gen_define_size_bits(f, s, ext, bits,
                msb_used or (sub_sp and ext), # because `gen_sub_sp` uses `msb`
                mask_used or changes_dst, # because `mask` used
                carry_used
            )

            yield gen_set_mem_size(f, s, True, ext, tcg_mem_size)

            if sub_sp:
                yield gen_sub_sp(f, s, ext, *bits)

            if save_pc:
                yield gen_save_pc(f, s, 6 if ext else 4)

            yield gen_get_operand_idx_code(f, s, ext, dst, doff, dst_val,
                tcg_mem_size,
                oper_mem_addr = mem_addr
            )

            res = tcg("res")
            yield semantics(f, s, dst_val, res, 6 if ext else 4, ext, *bits)

            if changes_dst:
                yield OpCombAssign(res, bits[1], "&") # mask
                yield gen_set_dst_code(f, s, True, res, tcg_mem_size, mem_addr)

        # dst: (indirect) register (autoincrement)
        disas_format = common_format + "<dst, ad>"

        if ext:
            # Register Mode Extension Word
            # Note, now used not only for Register mode, but for
            # (Indirect) Register (Autoincrement) mode.
            ext_word = [
                c(7, 0b0001100),
                o(1, "zc"),
                o(1, "rep"),
                o(1, "al"),
                c(2, 0b00),
                o(4, "reg_or_n") # depends on rep
            ]

            disas_format = "<rep, reg_or_n>" + disas_format

        fields = ext_word + [
            c(9, opcode),
            o(1, "bw"), # B/W
            o(2, "ad"), # (Ad == 00b) or (Ad == 10b) or (Ad == 11b and dst != 0)
            o(4, "dst") # Rdst
        ]

        kw["disas_format"] = disas_format
        kw["priority"] = 0

        def dst_reg_sem_iteration(f, s, ext, bits, tcg_mem_size):
            ad = f["ad"]
            dst = f["dst"]
            dst_val = tcg("dst_val")
            mem_addr = tcg("mem_addr")

            # XXX: add `gen_sub_sp` for properly PUSH generation

            if save_pc:
                yield gen_save_pc(f, s, 4 if ext else 2)

            yield gen_get_oper_reg_code(f, s, ext, ad, dst, dst_val,
                tcg_mem_size, 4 if ext else 2, # XXX: correct for X?
                0, # XXX: fix value
                sub_sp,
                oper_mem_addr = mem_addr
            )

            res = tcg("res")
            yield semantics(f, s, dst_val, res, 4 if ext else 2, ext, *bits)

            # Note: place here registers incrementation to solve problem with
            # @SP+ usage
            if sub_sp:
                yield BranchIf(
                    OpLogAnd(
                        OpLogAnd(
                            OpEq(ad, 3),
                            OpNEq(dst, 0)
                        ),
                        OpNEq(dst, 2)
                    )
                )(
                    gen_autoincrement(f, s, dst, s["regs"][dst - 1], ext)
                )

            if changes_dst:
                yield OpCombAssign(res, bits[1], "&") # mask
                yield BranchIf(ad)(
                    gen_set_dst_code(f, s, True, res, tcg_mem_size, mem_addr),
                    BranchElse()(
                        gen_set_dst_code(f, s, False, res, tcg_mem_size,
                            mem_addr
                        )
                    )
                )

        @i(name + "_reg", *fields, **kw)
        @wraps(semantics)
        @flat_list
        def dst_reg_sem(f, s, ext = ext):
            ad = f["ad"]
            tcg_mem_size = MemOp("size")

            bits = []
            yield gen_define_size_bits(f, s, ext, bits,
                msb_used or (sub_sp and ext), # because `gen_sub_sp` uses `msb`
                mask_used or changes_dst, # because `mask` used
                carry_used
            )

            yield BranchIf(ad)(
                gen_set_mem_size(f, s, True, ext, tcg_mem_size)
            )

            if sub_sp:
                yield gen_sub_sp(f, s, ext, *bits)

            if ext:
                # TODO: Zero carry (ext)

                reg_or_n = f["reg_or_n"]
                reps = tcg("reps")
                pc = OpSDeref(f["ctx"], "pc")

                yield BranchIf(f["rep"])(
                    BranchIf(reg_or_n)(
                        Comment("repetition count is in Rn[3:0] (not PC)"),
                        OpAssign(reps, s["regs"][reg_or_n - 1]),
                        BranchElse()(
                            Comment("repetition count is in PC[3:0]"),
                            OpAssign(reps, pc)
                        )
                    ),
                    OpCombAssign(reps, CINT("0x0000F"), "&"),
                    BranchElse()(
                        Comment("repetition count is immediate"),
                        OpAssign(reps, reg_or_n)
                    )
                )
                yield Comment("repetition count is kept one less")
                yield OpInc(reps)

                yield LoopWhile(OpDec(reps))(
                    dst_reg_sem_iteration(f, s, ext, bits, tcg_mem_size)
                )
            else:
                yield dst_reg_sem_iteration(f, s, ext, bits, tcg_mem_size)


def append_J(opcode_and_cond, name, semantics, **kw):
    "Conditional Jump"

    @i(name,
        c(6, opcode_and_cond),
        # c(3, opcode),
        # o(3, "cond"), # Condition
        # o(1, "s"), # S
        # o(9, "offset") # 10-Bit Signed PC Offset (s is 10-th bit)
        o(10, "offset"), # 10-Bit Signed PC Offset
        disas_format = name.upper() + "\\t <offset>",
        **kw
    )
    @wraps(semantics)
    @flat_list
    def j_sem(f, s):
        offset = f["offset"]
        yield semantics(f, s, offset)
        yield is_branch(f, s)


def append_A(opcode, name, semantics,
    changes_dst = True,
    reads_dst = True,
    **kw
):
    "(Extended) Address Instruction"

    msb, mask, carry = CINT("0x80000"), CINT("0xFFFFF"), CINT("100000")

    name += "a"

    @i(name + "_imm",
        c(4, 0),
        o(4, "imm", 1),
        c(2, 0b10),
        c(2, opcode),
        o(4, "dst"),
        o(16, "imm"),
        disas_format = name.upper() + "\\t #<imm>, <dst>",
        **kw
    )
    @flat_list
    def imm_and_reg_sem(f, s):
        src_val = tcg("src_val")

        yield OpAssign(src_val, f["imm"])

        if reads_dst:
            dst_val = tcg("dst_val")
            dst = f["dst"]
            yield BranchIf(dst)(
                OpAssign(dst_val, s["regs"][dst - 1]),
                BranchElse()(
                    OpAssign(dst_val, s["pc"])
                )
            )
        else:
            dst_val = None

        res = tcg("res")
        yield semantics(f, s, src_val, dst_val, res, msb, mask, carry)

        if changes_dst:
            yield gen_set_dst_reg_code(f, s, res)

    @i(name + "_reg",
        c(4, 0),
        o(4, "src"),
        c(2, 0b11),
        c(2, opcode),
        o(4, "dst"),
        disas_format = name.upper() + "\\t <src>, <dst>",
        **kw
    )
    @flat_list
    def reg_and_reg_sem(f, s):
        src = f["src"]
        src_val = tcg("src_val")

        yield BranchIf(src)(
            OpAssign(src_val, s["regs"][src - 1]),
            BranchElse()(
                OpAssign(src_val, s["pc"])
            )
        )

        if reads_dst:
            dst_val = tcg("dst_val")
            dst = f["dst"]
            yield BranchIf(src)(
                OpAssign(dst_val, s["regs"][dst - 1]),
                BranchElse()(
                    OpAssign(dst_val, s["pc"])
                )
            )
        else:
            dst_val = None

        res = tcg("res")
        yield semantics(f, s, src_val, dst_val, res, msb, mask, carry)

        if changes_dst:
            yield gen_set_dst_reg_code(f, s, res)


def append_R(opcode, name, semantics, **kw):
    "Extended Rotate Instructions"

    @i(name,
        c(4, 0),
        o(2, "imm"),
        c(2, opcode),
        c(3, 0b010),
        o(1, "aw"),
        o(4, "dst"),
        disas_format = name.upper() + ".<aw>\\t #<imm>, <dst>",
        **kw
    )
    @wraps(semantics)
    @flat_list
    def semantics_wrapper(f, s):
        dst = f["dst"]
        pc = s["pc"]
        dst_val = tcg("dst_val")

        yield BranchIf(dst)(
            OpAssign(dst_val, s["regs"][dst - 1]),
            BranchElse()(
                OpAssign(dst_val, pc)
            )
        )

        res = tcg("res")
        imm = f["imm"]

        yield semantics(f, s, dst_val, imm, res)

        yield BranchIf(dst)(
            OpAssign(s["regs"][dst - 1], res),
            BranchElse()(
                OpAssign(pc, res),
                is_branch(f, s)
            )
        )


# And some specific MOVAs
def append_mova(opcode, *operands, **kw):
    kw["disas_format"] = "MOVA\\t" + kw.pop("disas_suffix")

    read_src = kw.pop("read_src")
    write_dst = kw.pop("write_dst")

    @i("mova_%x" % opcode,
        c(4, 0),
        operands[0],
        c(1, 0),
        c(3, opcode),
        *operands[1:],
        **kw
    )
    @flat_list
    def semantics(f, s):
        val = tcg("val")
        yield read_src(f, s, val)
        yield write_dst(f, s, val)


def append_calla(opcode, *operands, **kw):
    kw["disas_format"] = "CALLA\\t" + kw.pop("disas_suffix")

    fields = (c(8, 0b00010011), c(4, opcode)) + operands
    i_bitsize = 0
    for f in fields:
        i_bitsize += f.bitsize
    instruction_size = i_bitsize // 8

    read_src = kw.pop("read_src")

    @i("calla_%x" % opcode, *fields, **kw)
    @flat_list
    def semantics(f, s):
        target_address = tcg("target_address")

        yield read_src(f, s, target_address)

        ret_pc = uint32_t("ret_pc")
        yield OpAssign(ret_pc, OpSDeref(f["ctx"], "pc") + instruction_size)

        ret_pc_low = tcg("ret_pc_low")
        yield OpAssign(ret_pc_low, ret_pc & CINT("0xFFFF"))

        ret_pc_high = tcg("ret_pc_high")
        yield OpAssign(ret_pc_high, ret_pc >> 16)

        sp = SP(f, s)
        flags = MO_UW | MO_TE

        # TODO: can it be done with MO_UL? using single tcg_gen_qemu_st_tl call
        # According to operation note in the docs, it's made in two memory
        # writes.
        yield OpAssign(sp, sp - 2)
        yield Call("tcg_gen_qemu_st_tl", ret_pc_high, sp, 0, flags)
        yield OpAssign(sp, sp - 2)
        yield Call("tcg_gen_qemu_st_tl", ret_pc_low, sp, 0, flags)

        yield is_branch(f, s)
        # set PC
        yield OpAssign(s["pc"], target_address)


# semantics sub-generators used in functions above


def gen_define_size_bits(f, s, ext, bits, msb_used, mask_used, carry_used):
    bits[:] = msb, mask, carry = int_("msb"), int_("mask"), int_("carry")

    carry_used = carry_used or mask_used

    if msb_used or carry_used:
        bw = f["bw"]

        bits_b = []
        bits_w = []
        bits_a = []
        if msb_used:
            bits_b.append(OpAssign(msb, CINT("0x80")))
            bits_w.append(OpAssign(msb, CINT("0x8000")))
            bits_a.append(OpAssign(msb, CINT("0x80000")))
        if carry_used:
            bits_b.append(OpAssign(carry, CINT("0x100")))
            bits_w.append(OpAssign(carry, CINT("0x10000")))
            bits_a.append(OpAssign(carry, CINT("0x100000")))

        bw_size = BranchIf(bw)(
            *bits_b
        )
        bw_size(
            BranchElse()(
                *bits_w
            )
        )

        if ext:
            al_size = BranchIf(bw)(
                Comment("address size mode"),
                *bits_a
            )
            al_size(
                BranchElse()(
                    Comment("reserved")
                )
            )

            yield BranchIf(f["al"])(
                bw_size,
                BranchElse()(
                    al_size
                )
            )
        else:
            yield bw_size

    if mask_used:
        yield OpAssign(mask, carry - 1)


def gen_sub_sp(f, s, ext, msb, mask, carry):
    sp = SP(f, s)

    if ext:
        yield BranchIf(OpLogOr(OpEq(msb, "0x80"), OpEq(msb, "0x8000")))(
            OpAssign(sp, sp - 2),
            BranchElse()(
                OpAssign(sp, sp - 4)
            )
        )
    else:
        yield OpAssign(sp, sp - 2)


def gen_save_pc(f, s, instruction_size):
    sp = SP(f, s)
    ret_pc = tcg("ret_pc")

    yield OpAssign(ret_pc, OpSDeref(f["ctx"], "pc") + instruction_size)
    yield Call("tcg_gen_qemu_st_tl", ret_pc, sp, 0, MO_UW | MO_TE)


def gen_set_mem_size(f, s, ad, ext, tcg_mem_size):
    if not ad:
        return

    bw = f["bw"]

    bw_size = BranchIf(bw)(
        OpAssign(tcg_mem_size, MO_UB),
        BranchElse()(
            OpAssign(tcg_mem_size, MO_UW)
        )
    )

    if ext:
        yield BranchIf(f["al"])(
            bw_size,
            BranchElse()(
                BranchIf(bw)(
                    Comment("address size mode"),
                    OpAssign(tcg_mem_size, MO_UL),
                    BranchElse()(
                        Comment("reserved")
                    )
                )
            )
        )
    else:
        yield bw_size


def gen_truncate_val(f, s, val, ext):
    bw = f["bw"]

    bw_branch = BranchIf(bw)(
        Comment("byte mode"),
        OpAssign(val, val & CINT("0xFF")),
        BranchElse()(
            Comment("word mode"),
            OpAssign(val, val & CINT("0xFFFF"))
        )
    )

    if ext:
        yield BranchIf(f["al"])(
            bw_branch,
            BranchElse()(
                BranchIf(bw)(
                    Comment("address size mode"),
                    OpAssign(val, val & CINT("0xFFFFF")),
                    BranchElse()(
                        Comment("reserved")
                    )
                )
            )
        )
    else:
        yield bw_branch


def gen_autoincrement(f, s, operand, reg_expr, ext):
    bw = f["bw"]

    # Note: SP always increments by 2
    bw_branch = BranchIf(OpLogAnd(bw, OpNEq(operand, 1)))(
        Comment("byte mode"),
        OpCombAssign(reg_expr, 1, "+"),
        BranchElse()(
            Comment("word mode"),
            OpCombAssign(reg_expr, 2, "+")
        )
    )

    if ext:
        yield BranchIf(f["al"])(
            bw_branch,
            BranchElse()(
                BranchIf(bw)(
                    Comment("address size mode"),
                    OpCombAssign(reg_expr, 4, "+"),
                    BranchElse()(
                        Comment("reserved")
                    )
                )
            )
        )
    else:
        yield bw_branch


def gen_set_cg2(f, s, val, mode, msb, mask, carry):
    return BranchSwitch(mode) (
        SwitchCase(3)(
            OpAssign(val, mask)
        ),
        SwitchCaseDefault()(
            OpAssign(val, mode)
        )
    )


def gen_get_operand_idx_code(f, s, ext, operand, op_off, val, tcg_mem_size,
    oper_mem_addr = None
):
    pc = OpSDeref(f["ctx"], "pc")
    regs = s["regs"]
    if oper_mem_addr is None:
        oper_mem_addr = tcg("oper_mem_addr")

    yield BranchSwitch(operand)(
        SwitchCase(0)(
            Comment("PC - symbolic mode"),
            OpAssign(oper_mem_addr, pc + (4 if ext else 2) + op_off),
            *gen_indexed_addr_wrapping(
                OpAdd(pc, 4 if ext else 2, parenthesis = True),
                oper_mem_addr, ext
            )
        ),
        SwitchCase(2)(
            Comment("SR - absolute mode"),
            OpAssign(oper_mem_addr, op_off)
        ),
        SwitchCase(3)(
            Comment("CG2 is handled in another place"),
            Call("assert", 0)
        ),
        SwitchCaseDefault()(
            Comment("indexed mode"),
            OpAssign(oper_mem_addr, regs[operand - 1] + op_off),
            *gen_indexed_addr_wrapping(regs[operand - 1], oper_mem_addr, ext)
        )
    )

    yield OpCombAssign(oper_mem_addr, CINT("0xFFFFF" if ext else "0x0FFFF"),
        "&"
    )

    yield Call("tcg_gen_qemu_ld_tl", val, oper_mem_addr, 0,
        tcg_mem_size | MO_TE
    )

    yield gen_truncate_val(f, s, val, ext)


def gen_get_oper_reg_code(f, s, ext, mode, operand, oper_val, tcg_mem_size,
    pc_offset, ad, deferred_increment,
    oper_mem_addr = None
):
    pc = OpSDeref(f["ctx"], "pc")
    regs = s["regs"]
    if oper_mem_addr is None:
        oper_mem_addr = tcg("oper_mem_addr")

    if deferred_increment:
        autoincrement = Comment(
            "Post increment for Indirect Register Autoincrement mode"
        )
    else:
        autoincrement = BranchIf(OpEq(mode, 3))(
            gen_autoincrement(f, s, operand, regs[operand - 1], ext)
        )

    yield BranchIf(OpLogAnd(OpEq(operand, 2), OpEq(mode, 2)))(
        Comment("CG1 R2, As == 0b10"),
        OpAssign(oper_val, 4),
        BranchElse(OpLogAnd(OpEq(operand, 2), OpEq(mode, 3)))(
            Comment("CG1 R2, As == 0b11"),
            OpAssign(oper_val, 8)
        ),
        BranchElse()(
            BranchSwitch(mode)(
                SwitchCase(0)(
                    Comment("Register mode"),
                    BranchIf(operand)(
                        OpAssign(oper_val, regs[operand - 1]),
                        BranchElse()(
                            # Note: PC points to the next instruction in
                            # Register mode
                            OpAssign(oper_val, pc + (pc_offset + 2 * ad))
                        )
                    )
                ),
                Comment(
                    "Indexed/Symbolic/Absolute/Immediate modes are"
                    " handled not here"
                ),
                SwitchCaseDefault()(
                    Comment("Indirect Register (Autoincrement) mode"),
                    BranchIf(operand)(
                        OpAssign(oper_mem_addr, regs[operand - 1]),
                        autoincrement,
                        BranchElse()(
                            OpAssign(oper_mem_addr, pc + pc_offset)
                        )
                    ),
                    Call("tcg_gen_qemu_ld_tl", oper_val, oper_mem_addr, 0,
                        tcg_mem_size | MO_TE
                    )
                )
            ),
            gen_truncate_val(f, s, oper_val, ext)
        )
    )


def gen_get_dst_mem_addr_func_body(f, s, ext):
    mem_addr = f["mem_addr"]
    pc = OpSDeref(f["ctx"], "pc")
    regs = s["regs"]
    dst = f["dst"]
    doff = f["doff"]
    pc_offset = f["pc_offset"]

    yield BranchSwitch(dst)(
        SwitchCase(0)(
            Comment("PC - symbolic mode"),
            OpAssign(mem_addr, pc + pc_offset + doff),
            *gen_indexed_addr_wrapping(
                OpAdd(pc, pc_offset, parenthesis = True),
                mem_addr, ext
            )
        ),
        SwitchCase(2)(
            Comment("SR - absolute mode"),
            OpAssign(mem_addr, doff)
        ),
        SwitchCaseDefault()(
            Comment("indexed mode"),
            OpAssign(mem_addr, regs[dst - 1] + doff),
            *gen_indexed_addr_wrapping(regs[dst - 1], mem_addr, ext)
        )
    )

    yield OpCombAssign(mem_addr, CINT("0xFFFFF" if ext else "0x0FFFF"), "&")


def gen_indexed_addr_wrapping(reg_val, addr, ext):
    if not ext:
        return

    # XXX: Which value of PC used? Old or new?
    # Indexed/Symbolic mode of MSP430 instruction in lower 64KiB
    yield BranchIf(OpLogNot(reg_val & CINT("0xF0000")))(
        OpCombAssign(addr, CINT("0x0FFFF"), "&")
    )


def gen_get_dst_code(f, s, ext, ad, dst_val, tcg_mem_size, mem_addr,
    pc_offset
):
    if ad:
        yield Call("tcg_gen_qemu_ld_tl", dst_val, mem_addr, 0,
            tcg_mem_size | MO_TE
        )
    else:
        pc = OpSDeref(f["ctx"], "pc")
        regs = s["regs"]
        dst = f["dst"]

        yield BranchIf(dst)(
            OpAssign(dst_val, regs[dst - 1]),
            BranchElse()(
                OpAssign(dst_val, pc + pc_offset)
            )
        )

    yield gen_truncate_val(f, s, dst_val, ext)


def gen_set_dst_code(f, s, ad, res, tcg_mem_size, mem_addr):
    if ad: # indexed/symbolic/absolute mode
        yield Call("tcg_gen_qemu_st_tl", res, mem_addr, 0,
            tcg_mem_size | MO_TE
        )
    else: # register mode
        yield gen_set_dst_reg_code(f, s, res)


def gen_set_dst_reg_code(f, s, res):
    regs = s["regs"]
    dst = f["dst"]
    # PC and SP are word aligned
    yield BranchIf(OpLess(dst, 2))(
        OpCombAssign(res, CINT("0xFFFFE"), "&")
    )

    yield BranchIf(dst)(
        OpAssign(regs[dst - 1], res),
        BranchIf(OpEq(dst, 2))(
            gen_helper_check_sr_machine_bits(f, s)
        ),
        BranchElse()(
            OpAssign(s["pc"], res),
            is_branch(f, s)
        )
    )


def SP(f, s):
    "PC is not in regs, so 0-th reg is SP (R1)"
    return s["regs"][0]


def SR(f, s):
    "1-th is SR (R2)"
    return s["regs"][1]


def set_sr_flag_if(f, s, flag, cond):
    sr = SR(f, s)
    return BranchIf(cond)(
        OpAssign(sr, sr | MCall(flag)),
        BranchElse()(
            reset_sr_flag(f, s, flag)
        )
    )


def set_sr_flag(f, s, flag):
    sr = SR(f, s)
    return OpAssign(sr, sr | MCall(flag))


def reset_sr_flag(f, s, flag):
    sr = SR(f, s)
    return OpAssign(sr, sr & ~MCall(flag))


def set_neg(f, s, res, msb):
    return set_sr_flag_if(f, s, "SR_N", res & msb)


def set_zero(f, s, res, mask):
    return set_sr_flag_if(f, s, "SR_Z", OpLogNot(res & mask))


def set_carry(f, s, res, carry):
    return set_sr_flag_if(f, s, "SR_C", res & carry)


def set_overflow(f, s, src, dst, res, msb, inv_sign):
    if inv_sign:
        # If `sub`straction is done by addition (~src + 1), the src's
        # sign is opposite.
        same_sign = (src ^ dst) & msb
    else:
        same_sign = OpLogNot((src ^ dst) & msb)

    diff_sign = (dst ^ res) & msb
    return set_sr_flag_if(f, s, "SR_V", OpLogAnd(same_sign, diff_sign))


def gen_set_flags(f, s, src, dst, res, msb, mask, carry):
    yield set_neg(f, s, res, msb)
    yield set_zero(f, s, res, mask)
    yield set_carry(f, s, res, carry)


def is_branch(f, s):
    # ctx->bstate = BS_BRANCH;
    return OpAssign(OpSDeref(f["ctx"], "bstate"), MCall("BS_BRANCH"))


def gen_call_autoinc_sp(f, s):
    sp = SP(f, s)

    dst_val = tcg("dst_val")
    mem_addr = tcg("mem_addr")
    ret_pc = tcg("ret_pc")

    flags = MO_UW | MO_TE

    yield OpAssign(ret_pc, OpSDeref(f["ctx"], "pc") + 2)
    yield Call("tcg_gen_qemu_st_tl", ret_pc, sp, 0, flags)

    yield OpAssign(mem_addr, sp - 2)
    yield Call("tcg_gen_qemu_ld_tl", dst_val, mem_addr, 0, flags)

    yield is_branch(f, s)

    # set PC
    yield OpAssign(s["pc"], dst_val)


def gen_reti_430(f, s):
    sp = SP(f, s)
    sr = SR(f, s)
    PC = s["pc"]
    flags = MO_UW | MO_TE

    yield Call("tcg_gen_qemu_ld_tl", sr, sp, 0, flags)
    yield OpCombAssign(sp, 2, "+")

    yield Call("tcg_gen_qemu_ld_tl", PC, sp, 0, flags)
    yield OpCombAssign(sp, 2, "+")

    yield is_branch(f, s)


def gen_reti_430x(f, s):
    sp = SP(f, s)
    sr = SR(f, s)
    PC = s["pc"]
    flags = MO_UW | MO_TE

    pc_19_16_and_sr = tcg("pc_19_16_and_sr")

    yield Call("tcg_gen_qemu_ld_tl", pc_19_16_and_sr, sp, 0, flags)
    yield OpCombAssign(sp, 2, "+")

    sr_mask = CINT("0x0FFF")
    yield OpAssign(sr, pc_19_16_and_sr & sr_mask)

    yield Call("tcg_gen_qemu_ld_tl", PC, sp, 0, flags)
    yield OpCombAssign(sp, 2, "+")

    pc_mask = CINT("0xF000")
    yield OpCombAssign(PC, pc_19_16_and_sr & pc_mask, "|")

    yield is_branch(f, s)


# read/write semantics for `append_mova` and `append_calla`


def write_dst_reg(f, s, dst_val):
    dst = f["dst"]
    yield BranchIf(dst)(
        OpAssign(s["regs"][dst - 1], dst_val),
        BranchElse()(
            OpAssign(s["pc"], dst_val),
            is_branch(f, s)
        )
    )


def read_src_indirect(f, s, src_val):
    src = f["src"]

    src_mem_addr = tcg("src_mem_addr")

    yield BranchSwitch(src)(
        SwitchCase(2)(
            Comment("CG1, There is no As but let it be 0b10 (indirect)"),
            OpAssign(src_val, CINT("0x00004"))
        ),
        SwitchCase(3)(
            Comment("CG2, There is no As but let it be 0b10 (indirect)"),
            OpAssign(src_val, CINT("0x00002"))
        ),
        SwitchCaseDefault()(
            BranchIf(src)(
                OpAssign(src_mem_addr,
                    s["regs"][src - 1]
                ),
                BranchElse()(
                    Comment("Symbolic mode"),
                    OpAssign(src_mem_addr, s["pc"])
                )
            ),
            Call("tcg_gen_qemu_ld_tl", src_val, src_mem_addr, 0,
                MO_UL | MO_TE
            ),
            OpCombAssign(src_val, CINT("0xFFFFF"), "&")
        )
    )


def read_src_autoincrement(f, s, src_val):
    src = f["src"]

    src_mem_addr = tcg("src_mem_addr")

    yield BranchSwitch(src)(
        SwitchCase(0)(
            Comment("There is another MOVA opcode for immediate mode"),
            Comment("TODO: gen_helper_illegal")
        ),
        SwitchCase(2)(
            Comment("CG1, There is no As but let it be 0b11 (autoincrement)"),
            OpAssign(src_val, CINT("0x00008"))
        ),
        SwitchCase(3)(
            Comment("CG2, There is no As but let it be 0b11 (autoincrement)"),
            OpAssign(src_val, CINT("0xFFFFF"))
        ),
        SwitchCaseDefault()(
            OpAssign(src_mem_addr, s["regs"][src - 1]),
            OpCombAssign(s["regs"][src - 1], 4, "+"),
            Call("tcg_gen_qemu_ld_tl", src_val, src_mem_addr, 0,
                MO_UL | MO_TE
            ),
            OpCombAssign(src_val, CINT("0xFFFFF"), "&")
        )
    )


def read_src_absolute(f, s, src_val):
    src_mem_addr = tcg("src_mem_addr")

    yield OpAssign(src_mem_addr, f["imm"])

    yield Call("tcg_gen_qemu_ld_tl", src_val, src_mem_addr, 0, MO_UL | MO_TE)

    yield OpCombAssign(src_val, CINT("0xFFFFF"), "&")


def read_src_indexed(f, s, src_val):
    src = f["src"]
    soff = f["soff"]

    src_mem_addr = tcg("src_mem_addr")

    yield BranchSwitch(src)(
        SwitchCase(0)(
            Comment("Symbolic mode"),
            OpAssign(src_mem_addr, s["pc"] + soff)
        ),
        SwitchCase(2)(
            Comment("There is another MOVA opcode for absolute mode, but..."),
            OpAssign(src_mem_addr, soff)
        ),
        SwitchCaseDefault()(
            OpAssign(src_mem_addr, s["regs"][src - 1] + soff)
        )
    )

    yield Call("tcg_gen_qemu_ld_tl", src_val, src_mem_addr, 0, MO_UL | MO_TE)

    yield OpCombAssign(src_val, CINT("0xFFFFF"), "&")


def read_src_reg(f, s, src_val):
    src = f["src"]
    yield BranchIf(src)(
        OpAssign(src_val, s["regs"][src - 1]),
        BranchElse()(
            OpAssign(src_val, s["pc"])
        )
    )


def write_dst_absolute(f, s, dst_val):
    dst_mem_addr = tcg("dst_mem_addr")
    yield OpAssign(dst_mem_addr, f["imm"])

    yield Call("tcg_gen_qemu_st_tl", dst_val, dst_mem_addr, 0, MO_UL | MO_TE)


def write_dst_indexed(f, s, dst_val):
    dst = f["dst"]
    doff = f["doff"]

    dst_mem_addr = tcg("dst_mem_addr")

    yield BranchSwitch(dst)(
        SwitchCase(0)(
            Comment("Symbolic mode"),
            OpAssign(dst_mem_addr, s["pc"] + doff)
        ),
        SwitchCase(2)(
            Comment("There is another MOVA opcode for absolute mode, but..."),
            OpAssign(dst_mem_addr, doff)
        ),
        # 3 CG2? There are no As mode bits, remember?
        SwitchCaseDefault()(
            OpAssign(dst_mem_addr, s["regs"][dst - 1] + doff)
        )
    )

    yield Call("tcg_gen_qemu_st_tl", dst_val, dst_mem_addr, 0, MO_UL | MO_TE)


# read/write semantics for `append_calla`


def read_src_symbolic(f, s, src_val):
    soff = f["soff"]
    src_mem_addr = tcg("src_mem_addr")
    yield OpAssign(src_mem_addr, s["pc"] + soff)

    yield Call("tcg_gen_qemu_ld_tl", src_val, src_mem_addr, 0, MO_UL | MO_TE)

    yield OpCombAssign(src_val, CINT("0xFFFFF"), "&")


def read_src_immediate(f, s, src_val):
    yield OpAssign(src_val, f["imm"])


# jump semantics generation helpers


def jump(f, s, offset):
    ctx_pc = OpSDeref(f["ctx"], "pc")

    target_offset = (
        OpAdd(ctx_pc, Call("extend_offset", offset) + 2, parenthesis = True) &
        CINT("0xFFFFF")
    )

    return OpAssign(s["pc"], target_offset)


def cond_jump(f, s, cond, offset):
    ctx_pc = OpSDeref(f["ctx"], "pc")

    return BranchIf(cond)(
        jump(f, s, offset),
        BranchElse()(
            OpAssign(s["pc"], ctx_pc + 2)
        )
    )


# helper calls


def gen_helper_check_sr_machine_bits(f, s):
    return Call("do_gen_helper_check_sr_machine_bits")


# common semantics


def ADD(f, s, src, dst, res, msb, mask, carry):
    "src + dst -> dst; NZCV; see INC, INCD, RLA;"

    yield OpAssign(res, src + dst)

    yield gen_set_flags(f, s, src, dst, res, msb, mask, carry)
    yield set_overflow(f, s, src, dst, res, msb, False)


def CMP(f, s, src, dst, res, msb, mask, carry):
    "~src + 1 + dst; NZCV;"

    yield OpAssign(res, (~src & mask) + 1)
    yield OpCombAssign(res, dst, "+")

    yield gen_set_flags(f, s, src, dst, res, msb, mask, carry)
    yield set_overflow(f, s, src, dst, res, msb, True)


def MOV(f, s, src, dst, res, *bits):
    "src -> dst; see BR, CLR, NOP, POP;"

    yield OpAssign(res, src)


def SUB(f, s, src, dst, res, msb, mask, carry):
    "~src + 1 + dst -> dst; NZCV; see DEC, DECD;"

    yield OpAssign(res, (~src & mask) + 1)
    yield OpCombAssign(res, dst, "+")

    yield gen_set_flags(f, s, src, dst, res, msb, mask, carry)
    yield set_overflow(f, s, src, dst, res, msb, True)


def append_common_instructions():

    # ADC -> ADDC #0, dst

    FI(5)(ADD)

    @FI(6)
    def ADDC(f, s, src, dst, res, msb, mask, carry):
        "src + dst + C -> dst; NZCV; see ADC, RLC;"

        # Looks like Carry bit is not accounted during oVerflow bit evaluation.
        yield OpAssign(res, src + dst)
        yield BranchIf(SR(f, s) & MCall("SR_C"))(
            OpInc(res)
        )
        yield gen_set_flags(f, s, src, dst, res, msb, mask, carry)
        yield set_overflow(f, s, src, dst, res, msb, False)

    @FI(0xF, carry_used = False)
    def AND(f, s, src, dst, res, msb, mask, carry):
        "src & dst -> dst; NZC; 0 -> V;"

        yield OpAssign(res, src & dst)
        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)

        # C: Set if result is not zero, reset otherwise (C = .not. Z)
        yield set_sr_flag_if(f, s, "SR_C", res & mask)

        yield reset_sr_flag(f, s, "SR_V")

    @FI(0xC, msb_used = False, mask_used = False, carry_used = False)
    def BIC(f, s, src, dst, res, *bits):
        "(~src) & dst -> dst; see CLRC, CLRN, CLRZ, DINT;"

        yield OpAssign(res, ~src & dst)

    @FI(0xD, msb_used = False, mask_used = False, carry_used = False)
    def BIS(f, s, src, dst, res, *bits):
        "src | dst -> dst; see EINT, SETC, SETN, SETZ;"

        yield OpAssign(res, src | dst)

    @FI(0xB, changes_dst = False, carry_used = False)
    def BIT(f, s, src, dst, res, msb, mask, carry):
        "src & dst; NZC; 0 -> V;"

        yield OpAssign(res, src & dst)
        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)

        yield set_sr_flag_if(f, s, "SR_C", res & mask)
        yield reset_sr_flag(f, s, "SR_V")

    # BR, BRANCH -> MOV dst, PC

    @FII(((0x10 + 2) << 1) | 1,
        changes_dst = False,
        has_ext = False,
        sub_sp = True,
        save_pc = True,
        msb_used = False,
        mask_used = False,
        carry_used = False
    )
    def CALL(f, s, dst, res, instruction_size, ext, *bits):
        "dst -> tmp; SP - 2 -> SP; PC -> @@SP; tmp & ~(0xF << 16) -> PC;"

        # Call is made within lower 64 K
        mask = CINT((1 << 16) - 1, base = 16)
        yield OpCombAssign(dst, mask, "&")

        yield is_branch(f, s)

        # set PC
        yield OpAssign(s["pc"], dst)

    # Note: extract "CALL @SP+" into separate case
    i("call_autoinc_sp", c(9, 0b000100101), o(1, "bw"), c(6, 0b110001),
        comment = "PC -> @@SP; @@(SP - 2) -> PC;",
        disas_format = "CALL.<bw>\\t @r1+",
        semantics = flat_list(gen_call_autoinc_sp)
    )

    # CLR -> MOV #0, dst

    # CLRC -> BIC #1, SR

    # CLRN -> BIC #4, SR

    # CLRZ -> BIC #2, SR

    FI(9, changes_dst = False)(CMP)

    # DADC -> DADD #0, dst

    @FI(0xA, carry_used = False)
    def DADD(f, s, src, dst, res, msb, mask, carry):
        "src + dst + C -> dst (decimally); Z; specific NC; see DADC;"

        # BCD arithmetics
        carry_outs = tcg("carry_outs")
        actual_carry_outs = tcg("actual_carry_outs")

        # Operands are at max 20 bit
        force_carry = OpAdd(src + dst, CINT("0x66666"), parenthesis = True)
        carry_ins = (src ^ dst) ^ force_carry

        yield OpAssign(carry_outs, (carry_ins >> 1) & CINT("0x88888"))

        yield OpAssign(actual_carry_outs, carry_outs - (carry_outs >> 2))

        yield OpAssign(res, src + dst + actual_carry_outs)

        force_carry = OpAdd(res + 1, CINT("0x66666"), parenthesis = True)
        carry_ins = (res ^ 1) ^ force_carry

        yield BranchIf(SR(f, s) & MCall("SR_C"))(
            OpAssign(carry_outs, (carry_ins >> 1) & CINT("0x88888")),
            OpAssign(actual_carry_outs, carry_outs - (carry_outs >> 2)),
            OpCombAssign(res, 1 + actual_carry_outs, "+")
        )

        yield OpCombAssign(res, mask, "&")

        # flags
        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)

        max_val = mask & CINT("0x99999")

        yield set_sr_flag_if(f, s, "SR_C", OpGreater(res, max_val))

    # DEC -> SUB #1, dst

    # DECD -> SUB #2, dst

    # DINT -> BIC #8, SR

    # EINT -> BIS #8, SR

    # INC -> ADD #1, dst

    # INCD -> ADD #2, dst

    # INV -> XOR #0FFFFh, dst

    @J(0x2C >> 2)
    def JC(f, s, offset):
        "if C: PC + 2 * offset -> PC;"

        yield cond_jump(f, s, SR(f, s) & MCall("SR_C"), offset)

    @J(0x24 >> 2)
    def JZ(f, s, offset):
        "if Z: PC + 2 * offset -> PC;"

        yield cond_jump(f, s, SR(f, s) & MCall("SR_Z"), offset)

    @J(0x34 >> 2)
    def JGE(f, s, offset):
        "if !(N ^ V): PC + 2 * offset -> PC;"

        # V is 8th bit and N is second.
        V_at_N = SR(f, s) >> 6

        yield cond_jump(f, s, OpLogNot((SR(f, s) ^ V_at_N) & MCall("SR_N")),
            offset
        )

    @J(0x38 >> 2)
    def JL(f, s, offset):
        "if (N ^ V): PC + 2 * offset -> PC;"

        V_at_N = SR(f, s) >> 6

        yield cond_jump(f, s, (SR(f, s) ^ V_at_N) & MCall("SR_N"), offset)

    @J(0x3C >> 2)
    def JMP(f, s, offset):
        "PC + 2 * offset -> PC;"

        yield jump(f, s, offset)

    @J(0x30 >> 2)
    def JN(f, s, offset):
        "if N: PC + 2 * offset -> PC;"

        yield cond_jump(f, s, SR(f, s) & MCall("SR_N"), offset)

    @J(0x28 >> 2)
    def JNC(f, s, offset):
        "if !C: PC + 2 * offset -> PC;"

        yield cond_jump(f, s, OpLogNot(SR(f, s) & MCall("SR_C")), offset)

    @J(0x20 >> 2)
    def JNE(f, s, offset):
        "if !Z: PC + 2 * offset -> PC;"

        yield cond_jump(f, s, OpLogNot(SR(f, s) & MCall("SR_Z")), offset)

    FI(4,
        reads_dst = False,
        msb_used = False,
        mask_used = False,
        carry_used = False
    )(MOV)

    # NOP -> MOV #0, R3

    # POP -> MOV @SP+, dst

    @FII(((0x10 + 2) << 1) | 0,
        changes_dst = False,
        sub_sp = True,
        mask_used = False,
        carry_used = False
    )
    def PUSH(f, s, dst, res, instruction_size, ext, msb, mask, carry):
        "SP - 2 -> SP; dst -> @@SP;"

        sp = SP(f, s)

        if ext:
            yield BranchIf(OpEq(msb, "0x80"))(
                Call("tcg_gen_qemu_st_tl", dst, sp, 0, MO_UB | MO_TE),
                BranchElse(OpEq(msb, "0x8000"))(
                    Call("tcg_gen_qemu_st_tl", dst, sp, 0, MO_UW | MO_TE)
                ),
                BranchElse()(
                    Call("tcg_gen_qemu_st_tl", dst, sp, 0, MO_UL | MO_TE)
                )
            )
        else:
            yield BranchIf(OpEq(msb, "0x80"))(
                Call("tcg_gen_qemu_st_tl", dst, sp, 0, MO_UB | MO_TE),
                BranchElse()(
                    Call("tcg_gen_qemu_st_tl", dst, sp, 0, MO_UW | MO_TE)
                )
            )

    # RET -> MOV @SP+, PC

    if with_ext:
        i("reti", c(16, 0x1300),
            comment = ("@@SP -> PC[19:16]|SR[11:0]; SP += 2; @@SP ->" +
                " PC[15:0]; SP += 2;"
            ),
            disas_format = "RETI",
            semantics = flat_list(gen_reti_430x)
        )
    else:
        i("reti", c(16, 0x1300),
            comment = "@@SP -> SR; SP += 2; @@SP -> PC; SP += 2;",
            disas_format = "RETI",
            semantics = flat_list(gen_reti_430)
        )

    # RLA -> ADD dst, dst

    # RLC -> ADDC dst, dst

    @FII(((0x10 + 1) << 1) | 0, carry_used = False)
    def RRA(f, s, dst, res, instruction_size, ext, msb, mask, carry):
        "dst[i] -> dst[i-1]; dst[MSB-1] -> dst[MSB]; i>MSB, 0 -> dst[i];"

        yield OpAssign(res, dst >> 1)

        yield OpCombAssign(res, dst & msb, "|")

        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)
        yield set_sr_flag_if(f, s, "SR_C", dst & 1)
        yield reset_sr_flag(f, s, "SR_V")

    @FII(((0x10 + 0) << 1) | 0, carry_used = False)
    def RRC(f, s, dst, res, instruction_size, ext, msb, mask, carry):
        "dst[LSB] -> C; dst[i] -> dst[i-1]; C -> dst[MSB];"

        yield OpAssign(res, dst >> 1)

        yield BranchIf(SR(f, s) & MCall("SR_C"))(
            OpCombAssign(res, msb, "|")
        )

        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)
        yield set_sr_flag_if(f, s, "SR_C", dst & 1)
        yield reset_sr_flag(f, s, "SR_V")

    # SBC -> SUBC #0, dst

    # SETC -> BIS #1, SR

    # SETN -> BIS #4, SR

    # SETZ -> BIS #2, SR

    FI(8)(SUB)

    @FI(7)
    def SUBC(f, s, src, dst, res, msb, mask, carry):
        "~src + C + dst -> dst; NZCV; see SBC;"

        yield OpAssign(res, (~src & mask) + dst)

        # Looks like Carry bit is not accounted during oVerflow bit evaluation.
        yield BranchIf(SR(f, s) & MCall("SR_C"))(
            OpInc(res)
        )

        yield gen_set_flags(f, s, src, dst, res, msb, mask, carry)
        yield set_overflow(f, s, src, dst, res, msb, True)

    @FII(((0x10 + 0) << 1) | 1, msb_used = False, carry_used = False)
    def SWPB(f, s, dst, res, instruction_size, ext, msb, mask, carry):
        "dst[0:7]->t; dst[8:15]->dst[0:7]; t->dst[8:15]; 0->dst[19:16];"

        yield OpAssign(res, dst >> 8)
        yield OpCombAssign(res, CINT("0xFF"), "&")
        yield OpCombAssign(res, dst << 8, "|")
        yield OpCombAssign(res, CINT("0xFFFF"), "&")

        yield BranchIf(OpEq(mask, CINT("0xFFFFF")))(
            Comment("address size (extended-only)"),
            OpCombAssign(res, dst & CINT("0xF0000"), "|")
        )

    @FII(((0x10 + 1) << 1) | 1,
        msb_used = False,
        mask_used = False,
        carry_used = False
    )
    def SXT(f, s, dst, res, instruction_size, ext, *bits):
        "dst[7]->dst[MSB:8] (different for mem and reg); NZCl 0 -> V;"

        yield BranchIf(dst & CINT("0x80"))(
            OpAssign(res, dst | CINT("0xFFF00")),
            BranchElse()(
                OpAssign(res, dst & CINT("0x000FF"))
            )
        )

        yield set_neg(f, s, res, CINT("0x80000"))
        yield set_zero(f, s, res, CINT("0xFFFFF"))

        # C: Set if result is not zero, reset otherwise (C = .not. Z)
        yield set_sr_flag_if(f, s, "SR_C", res & CINT("0xFFFFF"))

        yield reset_sr_flag(f, s, "SR_V")

    # TST -> CMP #0, dst

    @FI(0xE, carry_used = False)
    def XOR(f, s, src, dst, res, msb, mask, carry):
        "src ^ dst -> dst; NZCV; see INV;"

        yield OpAssign(res, src ^ dst)
        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)

        # C: Set if result is not zero, reset otherwise (C = .not. Z)
        yield set_sr_flag_if(f, s, "SR_C", res & mask)

        # V: Set if both operands are negative before execution,
        #    reset otherwise
        yield set_sr_flag_if(f, s, "SR_V", OpLogAnd(src & msb, dst & msb))


def gen_msp430_instructions():
    global with_ext
    with_ext = False
    del instructions[:]

    append_common_instructions()

    try:
        return list(instructions)
    finally:
        del instructions[:]


def gen_msp430x_instructions():
    global with_ext
    with_ext = True
    del instructions[:]

    # `append_common_instructions` also creates extended instructions when
    # `with_ext == True`:
    # ADCX (ADDCX), ADDX, ADDCX, ANDX, BICX, BISX, BITX, CLRX (MOVX), CMPX,
    # DADCX (DADDX), DADDX, DECX (SUBX), DECDX (SUBX), INCX (ADDX),
    # INCDX (ADDX), INVX (XORX), MOVX, ...
    append_common_instructions()

    @i("popm",
        c(7, 0b0001011),
        o(1, "aw"),
        o(4, "n_minus_1"),
        o(4, "dst"),
        disas_format = "POPM.<aw>\\t #<n_minus_1>, <dst, n_minus_1>"
    )
    @flat_list
    def popm(f, s):
        "Restore n CPU registers (20/16-bit data) from the stack"

        reg_n = int_("reg_n")
        last_reg = int_("last_reg")
        sp = SP(f, s)
        regs = s["regs"]
        reg_val = tcg("reg_val")

        yield OpAssign(reg_n, f["dst"])
        yield OpAssign(last_reg, reg_n + f["n_minus_1"])

        yield LoopFor(None, OpLE(reg_n, last_reg), OpInc(reg_n))(
            BranchIf(f["aw"])(
                Call("tcg_gen_qemu_ld_tl", reg_val, sp, 0, MO_UW | MO_TE),
                OpCombAssign(sp, 2, "+"),
                OpCombAssign(reg_val, "0x0FFFF", "&"),

                BranchElse()(
                    Call("tcg_gen_qemu_ld_tl", reg_val, sp, 0, MO_UL | MO_TE),
                    OpCombAssign(sp, 4, "+"),
                    OpCombAssign(reg_val, "0xFFFFF", "&")
                )
            ),
            BranchIf(reg_n)(
                OpAssign(regs[reg_n - 1], reg_val),
                BranchElse()(
                    OpAssign(s["pc"], reg_val),
                    is_branch(f, s)
                )
            )
        )

    @i("pushm",
        c(7, 0b0001010),
        o(1, "aw"),
        o(4, "n_minus_1"),
        o(4, "dst"),
        disas_format = "PUSHM.<aw>\\t #<n_minus_1>, <dst>"
    )
    @flat_list
    def pushm(f, s):
        "Save n CPU registers (20/16-bit data) on the stack"

        reg_n = int_("reg_n")
        last_reg = int_("last_reg")
        sp = SP(f, s)
        regs = s["regs"]
        reg_val = tcg("reg_val")

        yield OpAssign(reg_n, f["dst"])
        yield OpAssign(last_reg, reg_n - f["n_minus_1"])

        yield LoopFor(None, OpLE(last_reg, reg_n), OpDec(reg_n))(
            BranchIf(reg_n)(
                OpAssign(reg_val, regs[reg_n - 1]),
                BranchElse()(
                    OpAssign(reg_val, s["pc"])
                )
            ),
            BranchIf(f["aw"])(
                OpCombAssign(sp, 2, "-"),
                Call("tcg_gen_qemu_st_tl", reg_val, sp, 0, MO_UW | MO_TE),

                BranchElse()(
                    OpCombAssign(sp, 4, "-"),
                    OpCombAssign(reg_val, "0xFFFFF", "&"),
                    Call("tcg_gen_qemu_ld_tl", reg_val, sp, 0, MO_UL | MO_TE)
                )
            )
        )

    # by `append_common_instructions`:
    # ..., POPX (MOVX), PUSHX, ...

    @R(0b10)
    def RLAM(f, s, dst_val, imm, res):
        "C <- MSB <- ... <- LSB <- 0; NZC; V is undefined; aw == 0 -> .A;"

        n = uint32_t("n")
        yield OpAssign(n, imm + 1)

        mask, msb = uint32_t("mask"), uint32_t("msb")

        yield OpAssign(res, dst_val << n)

        yield BranchIf(f["aw"])(
            Comment("Word size"),
            OpAssign(mask, CINT("0xFFFF")),
            OpAssign(msb, CINT("0x8000")),

            BranchElse()(
                Comment("Address size"),
                OpAssign(mask, CINT("0xFFFFF")),
                OpAssign(msb, CINT("0x80000"))
            )
        )

        yield OpCombAssign(res, mask, "&")

        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)
        yield set_sr_flag_if(f, s, "SR_C", dst_val & (msb >> imm))

    # by `append_common_instructions`:
    # ..., RLAX (ADDX), RLCX (ADDCX), ...

    @R(0b01)
    def RRAM(f, s, dst_val, imm, res):
        "MSB -> MSB -> ... -> LSB -> C; NZC; 0 -> V; aw == 0 -> .A;"

        n = uint32_t("n")
        yield OpAssign(n, imm + 1)

        mask = uint32_t("mask")

        yield BranchIf(f["aw"])(
            Comment("Word size"),
            OpAssign(mask, CINT("0xFFFF")),
            OpAssign(res, (dst_val & CINT("0xFFFF")) >> n),
            BranchIf(dst_val & CINT("0x8000"))(
                OpCombAssign(res,
                    (
                        OpSub(1 << n, 1, parenthesis = True) <<
                        OpSub(16, n, parenthesis = True)
                    ),
                    "|"
                ),
                set_sr_flag(f, s, "SR_N"),
                BranchElse()(
                    reset_sr_flag(f, s, "SR_N")
                )
            ),

            BranchElse()(
                Comment("Address size"),
                OpAssign(mask, CINT("0xFFFFF")),
                OpAssign(res, dst_val >> n),
                BranchIf(dst_val & CINT("0x80000"))(
                    OpCombAssign(res,
                        (
                            OpSub(1 << n, 1, parenthesis = True) <<
                            OpSub(20, n, parenthesis = True)
                        ),
                        "|"
                    ),
                    set_sr_flag(f, s, "SR_N"),
                    BranchElse()(
                        reset_sr_flag(f, s, "SR_N")
                    )
                )
            )
        )

        yield OpCombAssign(res, mask, "&")

        yield set_zero(f, s, res, mask)
        yield set_sr_flag_if(f, s, "SR_C", dst_val & (1 << imm))
        yield reset_sr_flag(f, s, "SR_V")

    # by `append_common_instructions`:
    # ..., RRAX, ...

    @R(0b00)
    def RRCM(f, s, dst_val, imm, res):
        "C -> MSB -> ... -> LSB -> C; NZCV; aw == 0 -> .A;"

        n = uint32_t("n")
        yield OpAssign(n, imm + 1)

        mask, msb, carry = uint32_t("mask"), uint32_t("msb"), uint32_t("carry")

        yield BranchIf(f["aw"])(
            Comment("Word size"),
            OpAssign(mask, CINT("0xFFFF")),
            OpAssign(msb, CINT("0x8000")),
            OpAssign(res, (dst_val & CINT("0xFFFF")) >> n),
            BranchIf(SR(f, s) & MCall("SR_C"))(
                OpAssign(carry, CINT("0x10000") >> n),
                OpCombAssign(res, carry, "|")
            ),
            OpCombAssign(res, dst_val << OpSub(16, imm, parenthesis = True),
                "|"
            ),

            BranchElse()(
                Comment("Address size"),
                OpAssign(mask, CINT("0xFFFFF")),
                OpAssign(msb, CINT("0x80000")),
                OpAssign(carry, CINT("0x100000")),
                OpAssign(res, dst_val >> n),
                BranchIf(SR(f, s) & MCall("SR_C"))(
                    OpAssign(carry, CINT("0x100000") >> n),
                    OpCombAssign(res, carry, "|")
                ),
                OpCombAssign(res,
                    dst_val << OpSub(20, imm, parenthesis = True),
                    "|"
                )
            )
        )

        yield OpCombAssign(res, mask, "&")

        yield set_neg(f, s, res, msb)
        yield set_zero(f, s, res, mask)
        yield set_sr_flag_if(f, s, "SR_C", dst_val & (1 << imm))
        yield reset_sr_flag(f, s, "SR_V")

    # by `append_common_instructions`:
    # ..., RRCX, ...

    @R(0b11)
    def RRUM(f, s, dst_val, imm, res):
        "0 -> MAB -> ... -> LSB -> C; NZC; 0 -> V; aw == 0 -> .A;"

        n = uint32_t("n")
        yield OpAssign(n, imm + 1)

        mask = uint32_t("mask")

        yield OpAssign(res, dst_val >> n)

        yield BranchIf(f["aw"])(
            Comment("Word size"),
            OpAssign(mask, CINT("0xFFFF")),

            BranchElse()(
                Comment("Address size"),
                OpAssign(mask, CINT("0xFFFFF"))
            )
        )

        yield OpCombAssign(res, mask, "&")

        # Cannot be negative, because 0 is inserted into MSB
        yield reset_sr_flag(f, s, "SR_N")
        yield set_zero(f, s, res, mask)
        yield set_sr_flag_if(f, s, "SR_C", dst_val & (1 << imm))
        yield reset_sr_flag(f, s, "SR_V")

    # TODO: RRUX (no opcode in the docs)

    # by `append_common_instructions`:
    # ..., SBCX (SUBCX), ..., SUBX, SUBCX, SWPBX, SXTX, TSTX (CMPX), XORX

    # Address instructions

    append_A(0b10, "add",
        semantics = ADD,
        comment = "(src/imm) + dst -> dst; NZCV;"
    )

    # BRA -> MOVA dst, PC

    # CALLA
    append_calla(0b0100, o(4, "src"),
        disas_suffix = "<src>",
        comment = "register",
        read_src = read_src_reg
    )

    append_calla(0b0101, o(4, "src"), o(16, "soff"),
        disas_suffix = "<soff>(<src>)",
        comment = "indexed",
        read_src = read_src_indexed
    )

    append_calla(0b0110, o(4, "src"),
        disas_suffix = "@<src>",
        comment = "indirect",
        read_src = read_src_indirect
    )

    append_calla(0b0111, o(4, "src"),
        disas_suffix = "@<src>+",
        comment = "indirect autoincrement",
        read_src = read_src_autoincrement
    )

    append_calla(0b1000, o(4, "imm", 1), o(16, "imm"),
        disas_suffix = "&<imm>",
        comment = "absolute",
        read_src = read_src_absolute
    )

    append_calla(0b1001, o(4, "soff", 1), o(16, "soff"),
        disas_suffix = "<soff>",
        comment = "symbolic",
        read_src = read_src_symbolic
    )

    append_calla(0b1011, o(4, "imm", 1), o(16, "imm"),
        disas_suffix = "#<imm>",
        comment = "immediate",
        read_src = read_src_immediate
    )

    # CLRA -> MOVA #0, dst

    append_A(0b01, "cmp",
        semantics = CMP,
        changes_dst = False,
        comment = "~(src/imm) + 1 + dst; NZCV;"
    )

    # DECDA -> SUBA #2, dst

    # INCDA -> ADDA #2, dst

    # MOVA
    append_A(0b00, "mov",
        semantics = MOV,
        comment = "(src/imm) -> dst;",
        reads_dst = False
    )

    append_mova(0b000, o(4, "src"), o(4, "dst"),
        comment = "indirect src, register dst",
        disas_suffix = "@<src>, <dst>",
        read_src = read_src_indirect,
        write_dst = write_dst_reg
    )

    append_mova(0b001, o(4, "src"), o(4, "dst"),
        comment = "indirect autoincrement src, register dst",
        disas_suffix = "@<src>+, <dst>",
        read_src = read_src_autoincrement,
        write_dst = write_dst_reg
    )

    append_mova(0b010, o(4, "imm", 1), o(4, "dst"), o(16, "imm"),
        comment = "absolute src, register dst",
        disas_suffix = "&<imm>, <dst>",
        read_src = read_src_absolute,
        write_dst = write_dst_reg
    )

    append_mova(0b011, o(4, "src"), o(4, "dst"), o(16, "soff"),
        comment = "indexed src, register dst",
        disas_suffix = "<src, soff>, <dst>",
        read_src = read_src_indexed,
        write_dst = write_dst_reg
    )

    append_mova(0b110, o(4, "src"), o(4, "imm", 1), o(16, "imm"),
        comment = "register src, absolute dst",
        disas_suffix = "<src>, &<imm>",
        read_src = read_src_reg,
        write_dst = write_dst_absolute
    )

    append_mova(0b111, o(4, "src"), o(4, "dst"), o(16, "doff"),
        comment = "register src, indexed dst",
        disas_suffix = "<src>, <dst, doff>",
        read_src = read_src_reg,
        write_dst = write_dst_indexed
    )

    # RETA -> MOVA @SP+. PC

    # TSTA -> CMPA #0, dst

    append_A(0b11, "sub",
        semantics = SUB,
        comment = "~(src/imm) + 1 + dst -> dst; NZCV;"
    )

    try:
        return list(instructions)
    finally:
        del instructions[:]


# Byte, word or address size B/W/A
# A/L  B/W
#  0    0   reserved
#  0    1   20 bit (.A)
#  1    0   16 bit (.W)
#  1    1    8 bit (.B)
# See Non-Register Mode Extension Word description.
# Let B/W have same encoding for non-extended instructions (without A/L bit).
# This also different for SWPBX and SXTX instructions.
# A/L  B/W
#  0    0   .A
#  0    1   N/A
#  1    0   .W
#  1    1   N/A


# There are few functions automatizing instruction encoding definition.


def reg_types(s, ext):
    # CPU Status Register flags
    Macro("SR_C", text = "(1 << 0)")
    Macro("SR_Z", text = "(1 << 1)")
    Macro("SR_N", text = "(1 << 2)")
    Macro("SR_V", text = "(1 << 8)")

    extend_offset = Function(
        name = "extend_offset",
        ret_type = uint32_t,
        args = [ uint32_t("offset") ],
        static = True,
        inline = True
    )

    extend_offset.body = BodyTree()(
        BranchIf(extend_offset["offset"] & OpLShift(1, 9))(
            OpCombAssign(extend_offset["offset"], OpLShift(CINT("0x1FF"), 10),
                "|"
            )
        ),
        Return(extend_offset["offset"] << 1)
    )

    get_dst_mem_addr = Function(
        name = "get_dst_mem_addr",
        args = [
            tcg("mem_addr"),
            Pointer(Type["DisasContext"])("ctx"),
            uint64_t("dst"),
            uint64_t("doff"),
            uint64_t("pc_offset"),
        ],
        ret_type = Type["void"],
        static = True,
        inline = True
    )
    get_dst_mem_addr.body = BodyTree()(
       *gen_get_dst_mem_addr_func_body(get_dst_mem_addr, s, ext)
    )
    s.add_type(get_dst_mem_addr)

    s.add_type(Function(
        name = "do_gen_helper_check_sr_machine_bits",
        static = True,
        inline = True
    ))


def msp430_reg_types(source):
    reg_types(source, False)


def msp430x_reg_types(source):
    reg_types(source, True)


# Disas formatters


def gen_get_reg_name(f, s):
    """ get_reg used by several disas formatters. This way ensures that it
always be defined.
    """

    try:
        get_reg = Type["get_reg"]
    except TypeNotRegistered:
        reg = Type["unsigned"]("reg")

        get_reg = Function(
            name = "get_reg",
            ret_type = Pointer(Type["const char"]),
            args = [ reg ],
            static = True,
            inline = True
        )

        get_reg.body = BodyTree()(
            BranchIf(reg)(
                Return(s["regs"][reg - 1]),
                BranchElse()(
                    Return("pc")
                )
            )
        )

    return get_reg


def format_size(func, __):
    bw = func[0]
    bw.name = "bw"

    yield BranchIf(bw)(
        Return("B"),
        BranchElse()(
            Return("W")
        )
    )


def format_size_ex(func, *a):
    bw, al = func[0], func[1]
    bw.name = "bw"
    al.name = "al"

    ret = BranchIf(al)(
        *format_size(func, *a)
    )
    ret(BranchElse()(
        BranchIf(bw)(
            Return("A"),
            BranchElse()(
                Return("[reserved]")
            )
        )
    ))
    yield ret


def format_size_rot(func, __):
    aw = func[0]
    aw.name = "aw"

    yield BranchIf(aw)(
        Return("W"),
        BranchElse()(
            Return("A")
        )
    )


def format_reg(func, module):
    reg = func[0]
    reg.name = "reg"

    yield Return(Call(gen_get_reg_name(func, module), reg))


def print_indexed(func, module):

    def fpr(fmt, *args):
        fprintf = func[0]
        stream = func[1]
        offset = func[3]
        offset.name = "offset"
        return Call(fprintf, stream, fmt, offset, *args)

    reg = func[2]
    reg.name = "reg"

    yield BranchSwitch(reg)(
        SwitchCase(0)(
            Comment("symbolic"),
            fpr(
                StrConcat(
                    "0x%",
                    MCall("PRIx64"),
                    delim = "@s"
                )
            )
        ),
        SwitchCase(2)(
            Comment("absolute"),
            fpr(
                StrConcat(
                    "&0x%",
                    MCall("PRIx64"),
                    delim = "@s"
                )
            )
        ),
        SwitchCaseDefault()(
            Comment("indexed"),
            fpr(
                StrConcat(
                    "0x%",
                    MCall("PRIx64"),
                    "(%s)",
                    delim = "@s"
                ),
                module["regs"][reg - 1]
            )
        )
    )


def print_src(func, module):

    def fpr(fmt, *args):
        fprintf = func[0]
        stream = func[1]
        return Call(fprintf, stream, fmt, *args)

    reg = func[2]
    as_ = func[3]

    reg.name = "reg"
    as_.name = "as"

    reg_name = module["regs"][reg - 1]

    yield BranchSwitch(as_)(
        SwitchCase(0)(
            BranchSwitch(reg)(
                SwitchCase(0)(
                    fpr("pc")
                ),
                SwitchCase(3)(
                    Comment("CG2"),
                    fpr("#0")
                ),
                SwitchCaseDefault()(
                    fpr("%s", reg_name)
                )
            )
        ),
        SwitchCase(2)(
            BranchSwitch(reg)(
                SwitchCase(0)(
                    fpr("@pc")
                ),
                SwitchCase(2)(
                    Comment("CG1"),
                    fpr("#4")
                ),
                SwitchCase(3)(
                    Comment("CG2"),
                    fpr("#2")
                ),
                SwitchCaseDefault()(
                    fpr("@%s", reg_name)
                )
            )
        ),
        SwitchCase(3)(
            BranchSwitch(reg)(
                SwitchCase(0)(
                    fpr("; error: immediate mode must not be handled here")
                ),
                SwitchCase(2)(
                    Comment("CG1"),
                    fpr("#8")
                ),
                SwitchCase(3)(
                    Comment("CG2"),
                    fpr("#-1")
                ),
                SwitchCaseDefault()(
                    fpr("@%s+", reg_name)
                )
            )
        ),
        SwitchCaseDefault()(
            fpr(
                StrConcat(
                    "; error: As == %",
                    MCall("PRIu64"),
                    " must not be handled here",
                    delim = "@s"
                ),
                as_
            )
        )
    )


def format_cg2(func, __):
    mode = func[0]
    mode.name = "mode"

    yield BranchIf(OpEq(mode, 3))(
        Return(-1),
        BranchElse()(
            Return(mode)
        )
    )


def format_jump_offset(func, __):
    arg = func[0]
    yield Comment("sxxxxxxxxx0")
    yield BranchIf(arg & OpLShift(1, 9, parenthesis = True))(
        Comment("Note that 2 is size of a jump instruction."),
        # 2 - ((~(arg | ~0x3FFUL) + 1) << 1)
        Return(
            2 - (
                OpAdd(
                    ~(arg | OpNot(CINT("0x3FFUL"))),
                    1,
                    parenthesis = True
                ) << 1
            )
        ),
        BranchElse()(
            Return(2 + (arg << 1))
        )
    )


def print_rep(func, module):

    def fpr(fmt, *args):
        fprintf = func[0]
        stream = func[1]
        return Call(fprintf, stream, fmt, *args)

    rep, reg_or_n = func.args[-2:]
    rep.name = "rep"
    reg_or_n.name = "reg_or_n"

    yield BranchIf(rep)(
        fpr("RPT %s { ", Call(gen_get_reg_name(func, module), reg_or_n)),
        BranchElse()(
            fpr("RPT #%u { ", OpCast("unsigned", reg_or_n) + 1)
        )
    )


def inc_by_one(func, __):
    yield Return(func[0] + 1)


def format_reg_plus_n_minus_1(func, module):
    reg, n_minus_1 = func.args
    reg.name = "reg"
    n_minus_1.name = "n_minus_1"

    yield Return(Call(gen_get_reg_name(func, module), reg + n_minus_1))


name_to_format = {
    "bw": ("%s", flat_list(format_size)), # B or W
    "src": ("%s", flat_list(format_reg)), # register name
    "dst": ("%s", flat_list(format_reg)),
    "imm": ("0x%x", None), # hexadecimal immediate
    "soff": ("0x%x", None),
    "doff": ("0x%x", None),
    # X(Rn), X, &X depending on reg
    "dst, doff": (None, flat_list(print_indexed)),
    "src, soff": (None, flat_list(print_indexed)),
    "src, as": (None, flat_list(print_src)), # Rn, @Rn or @Rn+ depending on As
    "as": ("%d", flat_list(format_cg2)),
    "ad": ("%d", flat_list(format_cg2)), # for FII instructions
    "dst, ad": (None, flat_list(print_src)), # ad is 2-bit wide (as `As`) here
    # the offset requires special handling
    "offset": ("%d", flat_list(format_jump_offset)),
}

name_to_format_x = {
    "bw, al": ("%s", flat_list(format_size_ex)), # B or W or A
    "aw": ("%s", flat_list(format_size_rot)), # A or W
    # repetition mode of extended instructions
    "rep, reg_or_n": (None, flat_list(print_rep)),
    "n_minus_1": ("%u", flat_list(inc_by_one)), # see pushm/popm
    "dst, n_minus_1": ("%s", flat_list(format_reg_plus_n_minus_1)), # see popm
}
name_to_format_x.update(name_to_format)
