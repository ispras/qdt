from common.ply_tools import (
    gen_tokens,
)
from common.pypath import (
    pypath,
)
from .instruction import (
    Instruction,
    Operand,
    Opcode,
)
with pypath("..ply"):
    from ply.yacc import (
        yacc
    )
    from ply.lex import (
        lex
    )

from collections import (
    defaultdict,
)


_operand_part_min_bit = lambda operand : operand.num

class Short(object):

    t_ID = r"[a-zA-Z_]\w*"
    t_COLON = ":"
    t_CONCAT = r"\|"
    t_UINT = r"\d+"
    t_SPACE = r"[ ]"
    t_TAB = r"\t"
    t_LBRACKET = r"\["
    t_RBRACKET = r"\]"

    @staticmethod
    def t_NL(t):
        r"\r|\n|(\r\n)"
        t._short_last_nl = t.lexpos
        t.lexer.lineno += 1
        return t

    @staticmethod
    def t_error(t):
        print("%d.%d: unknown sequence of characters: %s" % (
            t.lineno,
            t.lexpos - getattr(t.lexer, "_short_last_nl", 0) + 1,
            t.value,
        ))

    @staticmethod
    def p_short(p):
        """short \
            : instruction
            | fields
        """
        p[0] = p[1]

    @staticmethod
    def p_bit_place(p):
        "bit_place : SPACE"
        p[0] = 1

    @staticmethod
    def p_bit_places(p):
        "bit_place : bit_place SPACE"
        p[0] = p[1] + 1

    @staticmethod
    def p_bit_place_ignored(p):
        """bit_place_ignored \
            : bit_place
            |
        """
        # ignored anyway...

    @staticmethod
    def p_opcode(p):
        "opcode : UINT bit_place_ignored"
        # Bit places are ignored for opcode.
        # They are for visual alignment only.
        # Opcode length is equal to length of token.
        UINT = p[1]
        p[0] = Opcode(len(UINT), val = int(UINT, base = 2))

    @staticmethod
    def p_operand(p):
        "operand : ID"
        ID = p[1]
        p[0] = Operand(len(ID), ID)

    @staticmethod
    def p_operand_long(p):
        "operand : ID bit_place"
        ID = p[1]
        bit_place = p[2]
        p[0] = Operand(len(ID) + bit_place, ID)

    @staticmethod
    def p_operand_len(p):
        "operand : ID COLON UINT bit_place_ignored"
        # Bit places are ignored if operand length is given explicitly.
        # They are for visual alignment only.
        ID = p[1]
        UINT = p[3]
        p[0] = Operand(int(UINT), ID)

    @staticmethod
    def p_operand_bit(p):
        "operand : ID LBRACKET UINT RBRACKET bit_place_ignored"
        ID = p[1]
        UINT = p[3]
        # `num` temporarly stores bit's position.
        # At end of parsing all same named `Operand`s will be sorted and `num`
        #    will be set to relative position index.
        p[0] = Operand(1, ID, num = int(UINT))

    @staticmethod
    def p_operand_part(p):
        "operand : ID LBRACKET UINT COLON UINT RBRACKET bit_place_ignored"
        ID = p[1]
        UINT_MAX = int(p[3])
        UINT_MIN = int(p[5])
        p[0] = Operand(UINT_MAX - UINT_MIN + 1, ID, num = int(UINT_MIN))

    @staticmethod
    def p_field(p):
        "field : operand \n| opcode"
        p[0] = p[1]

    @staticmethod
    def p_field_list_start(p):
        "fields_list : field"
        p[0] = [p[1]]

    @staticmethod
    def p_field_list(p):
        "fields_list : fields_list CONCAT field"
        p[0] = p[1] + [p[3]]

    @staticmethod
    def p_fields(p):
        "fields : fields_list"
        fields = p[1]
        # find out same named operands
        operands = defaultdict(list)
        for f in fields:
            if isinstance(f, Opcode):
                continue
            operands[f.name].append(f)

        for same_named_opers in operands.values():
            same_named_opers.sort(key = _operand_part_min_bit)

            offset = 0
            for i, o in enumerate(same_named_opers):
                if o.num != offset:
                    raise ValueError("operand %s bits [%u:%u] missed" % (
                        o.name, o.num - 1, offset
                    ))
                o.num = i
                offset += o.bitsize

        p[0] = fields

    @staticmethod
    def p_instruction(p):
        "instruction : ID whitespaces fields"
        ID = p[1]
        fields = p[3]
        p[0] = Instruction(ID, *fields)

    @staticmethod
    def p_whitespace(p):
        """whitespace \
            : bit_place
            | TAB
        """

    @staticmethod
    def p_whitespaces_start(p):
        "whitespaces : whitespace"

    @staticmethod
    def p_whitespaces(p):
        "whitespaces : whitespaces whitespace"

    @staticmethod
    def p_error(p):
        raise SyntaxError

    @staticmethod
    def parse(text, debug = False):
        return parser.parse(text, lexer = lexer.clone(), debug = debug)


Short.tokens = tuple(gen_tokens(Short.__dict__))
lexer = lex(
    object = Short,
    optimize = True,
    lextab = "_short_lextab",
)
parser = yacc(
    module = Short,
    tabmodule = "_short_parsetab",
    debugfile = "_short_yacc_debug.txt",
)
