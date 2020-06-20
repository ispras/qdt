__all__ = [
]

from .constants import (
    BYTE_SIZE,
    OPERAND_MAX_SIZE,
)
from source import (
    BranchSwitch,
    CINT,
    Comment,
    Declare,
    OpAnd,
    OpAssign,
    OpDeclareAssign,
    OpLShift,
    OpOr,
    OpRShift,
    SwitchCase,
    SwitchCaseDefault,
    Type,
)


class ParseTreeCodeBuilder(object):
    "This class traverses the instruction tree and builds the parsing code."

    def __init__(self, cputype, gen_node, gen_field_read_cb, epilogue_cb,
        result, default_switch_case_nodes,
        add_break = True
    ):
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
            val = Type["uint64_t"]("%d_%d" % (offset // BYTE_SIZE, length))
            val_desc = (val, offset, length)
            vals.append(val_desc)
            self.gen_field_read_cb(node, *val_desc)

        return vals

    def calc_shift_val(self, var_offset, var_length, offset, length):
        # Bytes in memory (address indicated):
        # [ 0 ][ 1 ][ 2 ][ 3 ]
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
        #
        # E.g. desired field has an offset == 18 and length == 5.
        # With such an offset it is in the `var1_16` variable
        # (var_offset == 16 and var_length == 16).
        #  var0_16           var1_16
        #  111111            111111
        #  5432109876543210  5432109876543210  bit indices in variables
        # [                ][                ]
        # [---------------->[                  var_offset == 16
        # [--------------------->(             offset == 18
        #                   [--->(             local_offset == 2
        #                        (field)       length == 5
        #                              )---->] shift_val (desired offset)
        #
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

    def gen_subtree_code(self, gen_node, instr_node, vars_desc = []):
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

                self.gen_subtree_code(sc, node, vars_desc = vars_desc)

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
