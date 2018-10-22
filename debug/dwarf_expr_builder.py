__all__ = [
    "DWARFExprBuilder"
]

from .expression import (
    Expression,

    DWARF_BINATY_OPS,
    Abs, Neg, Div, Minus, Mod, Mul, Plus, # arithmetic
    Shr, Not, And, Or, Shl, Shra, Xor, # bitwise logic
    Le, Ge, Eq, Lt, Gt, Ne, # comparison

    Dup,
    Register,
    FrameBase,
    AddressSize,
    Deref,
    ObjectAddress,
    ToTLS,
    CFA,
    Constant
)

import sys
from os.path import (
    split
)

# this module uses custom pyelftools
prev_path = list(sys.path)
sys.path.insert(0, split(__file__)[0])

from elftools.dwarf.dwarf_expr import (
    GenericExprVisitor,
    DW_OP_name2opcode
)

sys.path = prev_path


def unknown(opcode):
    print("Unknown opcode 0x%02x" % opcode)


class DWARFExprBuilder(GenericExprVisitor):
    """ Converts DWARF expression (DIE attribute's raw data) to `Expression`
    """

    def __init__(self, *args):
        super(DWARFExprBuilder, self).__init__(*args)
        # `stack` instance reference is cached in `_parser` and must never be
        # replaced
        self.stack = []
        self.parser_ctx = p = self._parser()
        next(p)

    def build(self, expr):
        """ Given DWARF expression it builds `Expression` instances graph.

    :param expr:
        a value of DIE attribute of form DW_FORM_exprloc

    :returns:
        an instance of `Expression`, the root node of built expression
        evaluation graph

        """
        del self.stack[:]

        self.process_expr(expr)

        res = self.stack[-1]

        if isinstance(res, Expression):
            return res
        else:
            # result can be an `int`eger
            return Constant(res)

    # internal methods

    def _parser(self):
        stack = self.stack
        append = stack.append
        pop = stack.pop
        ops = DW_OP_name2opcode

        # known opcodes will be overwritten below
        op = [ lambda _, opcode = i : unknown(opcode) for i in range (256) ]

        # constants in operand
        def push_arg(args):
            append(args[0])

        for op_name in ("DW_OP_addr", "DW_OP_const1u", "DW_OP_const2u",
            "DW_OP_const4u", "DW_OP_const8u", "DW_OP_const1s", "DW_OP_const2s",
            "DW_OP_const4s", "DW_OP_const8s", "DW_OP_constu", "DW_OP_consts"
        ):
            op[ops[op_name]] = push_arg

        # runtime data, part #1
        op[ops["DW_OP_deref"]] = lambda _ : append(
            Deref(pop(), AddressSize())
        )

        # stack operations
        def push(e):
            if isinstance(e, Expression):
                append(Dup(e))
            else: # int or long (under Py2)
                append(e)

        op[ops["DW_OP_dup"]] = lambda _ : push(stack[-1])
        op[ops["DW_OP_drop"]] = lambda _ : pop()
        op[ops["DW_OP_over"]] = lambda _ : push(stack[-2])
        op[ops["DW_OP_pick"]] = lambda args : push(stack[-(args[0] + 1)])

        def swap(_):
            a, b = stack[-2:]
            stack[-2:] = b, a

        op[ops["DW_OP_swap"]] = swap

        def rot(_):
            a, b, c = stack[-3:]
            stack[-3:] = c, a, b

        op[ops["DW_OP_rot"]] = rot

        # runtime data, part #2
        op[ops["DW_OP_xderef"]] = lambda _ : append(
            Deref(pop(), AddressSize(), address_space = pop())
        )

        # arithmetic and logic
        op[ops["DW_OP_plus_uconst"]] = lambda args : append(
            Plus(pop(), args[0])
        )

        for opcode_name, _ in DWARF_BINATY_OPS:
            cls = eval(opcode_name.title())

            op[ops["DW_OP_" + opcode_name]] = lambda _, c = cls : append(
                c(pop(), pop())
            )

        for opcode_name in ("abs", "neg", "not"):
            cls = eval(opcode_name.title())

            op[ops["DW_OP_" + opcode_name]] = lambda _, c = cls : append(
                c(pop())
            )

        def skip(_):
            raise NotImplementedError("skipping of DWARF expression operands"
                " is not implemented"
            )

        op[ops["DW_OP_skip"]] = skip

        def bra(_):
            raise NotImplementedError("branching in DWARF expressions is not"
                " implemented"
            )

        op[ops["DW_OP_bra"]] = bra

        def call(_):
            raise NotImplementedError("branching in DWARF expressions is not"
                " implemented"
            )

        op[ops["DW_OP_call2"]] = call
        op[ops["DW_OP_call4"]] = call

        def call_ref(_):
            raise NotImplementedError("branching in DWARF expressions is not"
                " implemented"
            )

        op[ops["DW_OP_call_ref"]] = call_ref

        # constant (literal)
        for opcode in range(0x30, 0x50):

            def push_const(_, c = opcode - 0x30):
                append(c)

            op[opcode] = push_const

        # runtime data, part #3
        # register
        for opcode in range(0x50, 0x70):

            def push_reg(_, idx = opcode - 0x50):
                append(Register(idx))

            op[opcode] = push_reg

        # register plus offset
        for opcode in range(0x70, 0x90):

            def push_reg_off(args, idx = opcode - 0x70):
                append(Plus(Register(idx), args[0]))

            op[opcode] = push_reg_off

        op[ops["DW_OP_fbreg"]] = lambda args : append(
            Plus(FrameBase(), args[0])
        )
        op[ops["DW_OP_bregx"]] = lambda args : append(
            Plus(Register(args[0]), args[1])
        )
        op[ops["DW_OP_deref_size"]] = lambda args : append(
            Deref(pop(), args[0])
        )
        op[ops["DW_OP_xderef_size"]] = lambda args : append(
            Deref(pop(), args[0], address_space = pop())
        )
        op[ops["DW_OP_nop"]] = lambda _ : None
        op[ops["DW_OP_push_object_address"]] = lambda _ : append(
            ObjectAddress()
        )
        op[ops["DW_OP_form_tls_address"]] = lambda _ : append(
            ToTLS(pop())
        )
        op[ops["DW_OP_call_frame_cfa"]] = lambda _ : append(CFA())

        while True:
            opcode, _, args = yield
            op[opcode](args)

    def _after_visit(self, opcode, opcode_name, args):
        self.parser_ctx.send((opcode, opcode_name, args))
