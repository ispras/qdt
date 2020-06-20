__all__ = [
    "ParseTreeCodeBuilder"
]

from .constants import (
    BYTE_BITSIZE,
    OPERAND_MAX_BITSIZE,
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
        default_switch_case_nodes,
        add_break = True
    ):
        """
    :param cputype:
        instance of `CPUType`

    :param gen_node:
        source.function.tree Node where to add code

    :param gen_field_read_cb:
        callback function that generates the code to readings

    :param epilogue_cb:
        callback function that generates processing of one instruction

    :param default_switch_case_nodes:
        list of nodes to insert when there is no `default` opcode in the
        instruction subtree

    :param add_break:
        flag indicating the need to add a break to the `default` branch made
        from `default_switch_case_nodes` list
        """

        instruction_tree_root = cputype.instruction_tree_root
        if not instruction_tree_root:
            gen_node(*default_switch_case_nodes)
            return

        self.target_bigendian = cputype.target_bigendian
        self.read_bitsize = cputype.read_bitsize
        self.gen_field_read_cb = gen_field_read_cb
        self.epilogue_cb = epilogue_cb
        self.default_switch_case = SwitchCaseDefault(add_break = add_break)(
            *default_switch_case_nodes
        )

        # divide vars by purpose
        self.opcode_vars = set()
        self.operand_vars = set()
        self.vars = set()

        self.gen_subtree_code(gen_node, instruction_tree_root)

        # auto naming vars by purpose
        for var in self.opcode_vars:
            var.name = "opc" + var.name
        for var in self.operand_vars - self.opcode_vars:
            var.name = "val" + var.name
        for var in self.vars - self.operand_vars - self.opcode_vars:
            var.name = "res" + var.name

    def gen_subtree_code(self, gen_node, instr_node, vars_desc = []):
        ins = instr_node.instruction

        if ins is not None:
            text = ins.comment
            gen_node(Comment(text))

        new_vars = []
        for offset, length in instr_node.reading_seq:
            # Note, a variable name can't start with a digit but a semantic
            # prefix will be assigned at the end of code generation.
            var = Type["uint64_t"]("%d_%d" % (offset // BYTE_BITSIZE, length))
            var_desc = (var, offset, length)
            new_vars.append(var_desc)
            self.gen_field_read_cb(gen_node, *var_desc)

        if new_vars is not None:
            vars_desc = vars_desc + new_vars
            self.vars.update(v[0] for v in new_vars)

        if ins is None:
            offset, length = instr_node.interval
            var, shift = self.get_var_and_shift(offset, length, vars_desc)

            cases = []
            default_sc = None
            for opcode, node in instr_node.subtree.items():
                if opcode == "default":
                    sc = default_sc = SwitchCaseDefault()
                else:
                    sc = SwitchCase(
                        CINT(
                            int(opcode, base = 2) << shift,
                            base = 16
                        )
                    )
                    cases.append(sc)

                self.gen_subtree_code(sc, node, vars_desc = vars_desc)

            if default_sc is not None:
                cases.append(default_sc)
            else:
                # If subtree hasn't `default` opcode we have to process an
                # unknown instruction, that is, exit the cpu loop or print
                # message about it in default branch.
                cases.append(self.default_switch_case)

            opc_mask = ((1 << length) - 1) << shift

            self.opcode_vars.add(var)
            gen_node(
                BranchSwitch(
                    OpAnd(var, CINT(opc_mask, base = 16)),
                    cases = cases
                )
            )
        else:
            operands = self.get_operands(gen_node, ins, vars_desc)
            total_read = (vars_desc[-1][1] + vars_desc[-1][2]) // BYTE_BITSIZE
            self.epilogue_cb(gen_node, ins, operands, total_read, text)

    def get_var_and_shift(self, offset, length, vars_desc):
        # looking for a variable that contains the desired interval
        for var, var_offset, var_length in reversed(vars_desc):
            if (    var_offset <= offset
                and offset + length <= var_offset + var_length
            ):
                break

        local_offset = offset - var_offset

        # We must account the endianness of CPU if the variable length is
        # larger than the read size.
        if self.target_bigendian:
            shift = var_length - length - local_offset
        else:
            swap_size = self.read_bitsize
            # TODO: explain the derivation of the formula
            shift = (swap_size + local_offset -
                2 * (local_offset % swap_size) - length
            )

        return var, shift

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
                var, shift_var = self.get_var_and_shift(
                    oper.offset, oper.length, vars_desc
                )
                self.operand_vars.add(var)
                oper_part = OpAnd(
                    OpRShift(var, shift_var) if shift_var else var,
                    CINT((1 << oper.length) - 1, base = 16),
                    # Prevent warning [-Wparentheses]
                    # "suggest parentheses around arithmetic in operand of `|`"
                    # when the operand is merged from several parts.
                    parenthesis = need_parenthesis
                )

                if shift:
                    oper_part = OpLShift(oper_part, shift)
                rval = OpOr(rval, oper_part) if rval else oper_part
                shift += oper.length

            if shift > OPERAND_MAX_BITSIZE:
                raise NotImplementedError('The operand "%s" in the instruction'
                    ' "%s" longer than %d bits. Please reduce the length'
                    " manually by breaking it into several operands." % (
                        name, instruction.mnemonic, OPERAND_MAX_BITSIZE
                    )
                )

            res = Type["uint64_t"](name)
            operands.append(res)
            declarations.append(Declare(OpDeclareAssign(res, rval)))

        node(*declarations)
        return operands
