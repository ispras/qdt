from source.short_ply_grammar import (
    short_ply_grammar,
)
from .instruction import (
    Instruction,
    Operand,
    operand_num_from_bitoffset,
    Opcode,
)

@short_ply_grammar(
    debugfile = True,
)
class Short(object):

    t_ID = r"[a-zA-Z_]\w*"
    t_COLON = ":"
    t_CONCAT = r"\|"
    t_UINT = r"\d+"
    t_SPACE = r"[ ]"
    t_LBRACKET = r"\["
    t_RBRACKET = r"\]"

    @staticmethod
    def t_error(t):
        raise SyntaxError("%d: unknown sequence of characters: %s" % (
            t.lexpos + 1,
            t.value,
        ))

    @staticmethod
    def s_short__0(instruction):
        return instruction

    @staticmethod
    def s_short__1(fields):
        return fields

    @staticmethod
    def s_bit_place__1(SPACE):
        return 1

    @staticmethod
    def s_bit_place__n(bit_place, SPACE):
        return bit_place + 1

    @staticmethod
    def s_bit_place_ignored__0(bit_place):
        # Bit places are ignored if operand length is given explicitly.
        # They are for visual alignment only.
        # Bit places are always ignored for opcodes.
        # Use explicit leading zeros.
        pass

    @staticmethod
    def s_bit_place_ignored__1():
        pass

    @staticmethod
    def s_opcode(UINT):
        # Bit places are ignored for opcode.
        # They are for visual alignment only.
        # Opcode length is equal to length of token.
        return Opcode(len(UINT), val = int(UINT, base = 2))

    @staticmethod
    def s_operand_na(ID):
        # not aligned
        return Operand(len(ID), ID)

    @staticmethod
    def s_operand_la(ID, bit_place):
        # left aligned
        return Operand(len(ID) + bit_place, ID)

    @staticmethod
    def s_operand_ra(bit_place, ID):
        # right aligned
        return Operand(len(ID) + bit_place, ID)

    @staticmethod
    def s_operand_ma(bit_place__l, ID, bit_place__r):
        # middle aligned
        return Operand(len(ID) + bit_place__l + bit_place__r, ID)

    @staticmethod
    def s_operand_el(ID, COLON, UINT):
        # explicit lenght
        return Operand(int(UINT), ID)

    @staticmethod
    def s_operand_el__bit(ID, LBRACKET, UINT, RBRACKET):
        # When an operand is fragmented in spread parts of the instruction word
        # this production represent one bit of the operand.
        # Brackets then encloses position of the bit inside the operand.
        # `num` temporarly stores bit's position.
        # At end of parsing all same named `Operand`s will be sorted and `num`
        #    will be set to relative position index.
        return Operand(1, ID, num = int(UINT))

    @staticmethod
    def s_operand_el__part(ID, LBRACKET, UINT__0, COLON, UINT__1, RBRACKET):
        # When an operand is fragmented in spread parts of the instruction word
        # this production represent one continuous part of the operand.
        # Brackets then encloses position of this part inside the operand.
        # The position is given as first and last bit indices
        # separated by colon (:)
        # This also implicitly defines the part length.
        UINT_MAX = int(UINT__0)
        UINT_MIN = int(UINT__1)
        return Operand(UINT_MAX - UINT_MIN + 1, ID, num = int(UINT_MIN))

    @staticmethod
    def s_field__1(first_field):
        return first_field

    @staticmethod
    def s_field__ra(operand_ra):
        return operand_ra

    @staticmethod
    def s_field__ma(operand_ma):
        return operand_ma

    @staticmethod
    def s_field__el(bit_place, operand_el, bit_place_ignored):
        return operand_el

    @staticmethod
    def s_field__o(bit_place, opcode, bit_place_ignored):
        return opcode

    @staticmethod
    def s_first_field__0(operand_el, bit_place_ignored):
        return operand_el

    @staticmethod
    def s_first_field__1(operand_na):
        return operand_na

    @staticmethod
    def s_first_field__2(operand_la):
        return operand_la

    @staticmethod
    def s_first_field__3(opcode, bit_place_ignored):
        return opcode

    @staticmethod
    def s_fields_list__start(first_field):
        return [first_field]

    @staticmethod
    def s_fields_list(fields_list, CONCAT, field):
        return fields_list + [field]

    @staticmethod
    def s_fields(fields_list):
        operand_num_from_bitoffset(fields_list)
        return fields_list

    @staticmethod
    def s_instruction(ID, bit_place, fields):
        return Instruction(ID, *fields)

    @staticmethod
    def p_error(p):
        raise SyntaxError
