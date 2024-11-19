__all__ = [
    "COp"
]


class COp:

    t_RARROW = "->"

    t_DEC = "--"
    t_INC = r"\+\+"
    t_QUEST = r"\?"

    t_BIT_AND = "&"
    t_BIT_OR = r"\|"
    t_BIT_XOR = r"\^"
    t_LOG_AND = "&&"
    t_LOG_OR = r"\|\|"

    t_STAR = r"\*"
    t_PLUS = r"\+"

    t_MINUS = "-"
    t_TILDE = "~"
    t_LOG_NOT = "!"
    t_PERCENT = "%"
    t_SLASH = "/"
    t_LSHIFT = "<<"
    t_RSHIFT = ">>"

    t_ASSIGN = "="
    t_COMB_ASSIGN = r"(\*|\/|%|\+|-|(<<)|(>>)|&|\^|\|)="

    t_LT = "<"
    t_GT = ">"
    t_LE = "<="
    t_GE = ">="
    t_EQ = "=="
    t_NE = "!="
