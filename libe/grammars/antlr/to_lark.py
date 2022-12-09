from lark import (
    Transformer,
)

class ANTLR2Lark(Transformer):

    def terminal(self, s):
        tmp = s[0]
        if tmp[0] == "'":
            tmp = tmp.value[1:-1]
            tmp = tmp.replace("\\'", "'")
            tmp = tmp.replace('"', '\\"')
            return '"' + tmp + '"'
        else:
            return tmp

    def lexer_atom(self, s):
        return s[0]

    def character_range(self, s):
        return '"' + s[0].value[1:-1] + '" .. "' + s[2].value[1:-1] + '"'

    def not_set(self, s):
        raise NotImplementedError("not_set")

    def lexer_char_set(self, s):
        tmp = s[0].value.replace("/", "\\/")
        return "/" + tmp + "/"

    def any_char(self, s):
        return "/./"

    def lexer_element(self, s):
        return " ".join(e for e in s if e is not None)

    def action_block(self, s):
        return None

    def ebnf_suffix(self, s):
        return "".join(e.value for e in s)

    def opt_action_block(self, s):
        return None

    def labeled_lexer_element(self, s):
        raise NotImplementedError("labeled_lexer_element")

    def lexer_block(self, s):
        return "(" + " | ".join(s[1]) + ")"

    def lexer_alt_list(self, s):
        alts = []
        for i, a in enumerate(s):
            if i & 1 == 0:
                alts.append(a)
        return alts

    def lexer_alt(self, s):
        return s[0]

    def lexer_elements(self, s):
        return " ".join(s)

    def lexer_rule_block(self, s):
        return s[0]

    def lexer_rule_spec(self, s):
        if s[0].type == "FRAGMENT":
            s = s[1:]

        return s[0] + ": " + " | ".join(s[2])

    def rule_spec(self, s):
        return s[0]

    def rules(self, s):
        return "\n".join(s)

    def grammar_spec(self, s):
        return "\n".join(s[1:])

    def mode_spec(self, s):
        return "\n".join(s[3:])

    def parser_rule_spec(self, s):
        if s[0].type == "rule_modifiers":
            s = s[1:]

        ref = s[0]

        siter = iter(s[1:])
        for i in siter:
            if i.type == "COLON":
                break

        rule_block = next(siter)

        return ref + ": " + " | ".join(rule_block)

    def rule_block(self, s):
        return s[0]

    def rule_alt_list(self, s):
        alts = []
        for i, labeled_alt in enumerate(s):
            if i & 1 == 0:
                alts.append(labeled_alt)
        return alts

    def labeled_alt(self, s):
        if len(s) > 1:
            raise NotImplementedError
        return s[0]

    def alternative(self, s):
        if len(s) == 0:
            return ""

        if not isinstance(s[0], str):
            # element_options
            s = s[1:]
        return " ".join(s)

    def element(self, s):
        return " ".join(e for e in s if e is not None)

    def labeled_element(self, s):
        raise NotImplementedError("labeled_element")

    def atom(self, s):
        return s[0]

    def ruleref(self, s):
        return s[0].value

    def block(self, s):
        return " | ".join(s[-2])  # alt_list

    def alt_list(self, s):
        alts = []
        for i, alt in enumerate(s):
            if i & 1 == 0:
                alts.append(alt)
        return alts
