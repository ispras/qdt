__all__ = [
    "antlr_4_grammar",
    "antlr_4_parser",
]

from lark import (
    Lark,
)


grammar = r"""
%import common.HEXDIGIT

WS: HWS | VWS
HWS: /[ \t]/
VWS: "\r" | "\n" | "\f"
BLOCK_COMMENT: "/*" /(.|\n|\r)*?/ "*/"
DOC_COMMENT: "/**" /(.|\n\r)*?/"*/"
LINE_COMMENT: "//" /[^\r\n]*/
ESCSEQ: ESC ( /[btnfr"'\\]/ | UESC | /./ )
UESC: "u" (HEXDIGIT (HEXDIGIT (HEXDIGIT HEXDIGIT?)?)?)?
DEC_NUM: "0" | /[1-9]/ DECDIGIT*
DECDIGIT: /[0-9]/
STRING_LITERAL: SQUOTE (ESCSEQ | /[^'\r\n\\]/ )* SQUOTE
UNTERMINATED_STRING_LITERAL: SQUOTE (ESCSEQ | /[^'\r\n\\]/ )*

UNDERSCORE: "_"

NAME_CHAR \
   : NAME_START_CHAR
   | "0" .. "9"
   | UNDERSCORE
   | "\u00B7"
   | "\u0300" .. "\u036F"
   | "\u203F" .. "\u2040"

NAME_START_CHAR \
   : "A" .. "Z"
   | "a" .. "z"
   | "\u00C0" .. "\u00D6"
   | "\u00D8" .. "\u00F6"
   | "\u00F8" .. "\u02FF"
   | "\u0370" .. "\u037D"
   | "\u037F" .. "\u1FFF"
   | "\u200C" .. "\u200D"
   | "\u2070" .. "\u218F"
   | "\u2C00" .. "\u2FEF"
   | "\u3001" .. "\uD7FF"
   | "\uF900" .. "\uFDCF"
   | "\uFDF0" .. "\uFFFD"

ESCANY: ESC /./

ESC: "\\"
COLON: ":"
COLONCOLON: "::"
SQUOTE: "'"
LPAREN: "("
RPAREN: ")"
LBRACE: "{"
RBRACE: "}"
LBRACK: "["
RARROW: "->"
LT: "<"
GT: ">"
EQ: "="
QUESTION: "?"
STAR: "*"
PLUS: "+"
PLUS_ASSIGN: "+="
PIPE: "|"
DOLLAR: "$"
COMMA: ","
SEMI: ";"
DOT: "."
RANGE: ".."
AT: "@"
POUND: "#"
TILDE: "~"

%ignore DOC_COMMENT
%ignore BLOCK_COMMENT
%ignore LINE_COMMENT

INT: DEC_NUM
BEGIN_ARGUMENT: LBRACK
BEGIN_ACTION: LBRACE
OPTIONS: "options" WS* LBRACE
TOKENS: "tokens" WS* LBRACE
CHANNELS: "channels" WS* LBRACE
IMPORT: "import"
FRAGMENT: "fragment"
LEXER: "lexer"
PARSER: "parser"
GRAMMAR: "grammar"
PROTECTED: "protected"
PUBLIC: "public"
PRIVATE: "private"
RETURNS: "returns"
LOCALS: "locals"
THROWS: "throws"
CATCH: "catch"
FINALLY: "finally"
MODE: "mode"
ASSIGN: EQ
OR: PIPE
NOT: TILDE
ID: NAME_START_CHAR NAME_CHAR*

%ignore WS

grammar_spec: grammar_header rules mode_spec*
grammar_header: grammar_decl prequel_construct*
grammar_decl: grammar_type identifier SEMI
grammar_type: (LEXER GRAMMAR | PARSER GRAMMAR | GRAMMAR)

prequel_construct \
   : options_spec
   | delegate_grammars
   | tokens_spec
   | channels_spec
   | action_

options_spec: OPTIONS (option SEMI)* RBRACE
option: identifier ASSIGN option_value

option_value \
   : identifier (DOT identifier)*
   | STRING_LITERAL
   | action_block
   | INT

delegate_grammars: IMPORT delegate_grammar (COMMA delegate_grammar)* SEMI

delegate_grammar \
   : identifier ASSIGN identifier
   | identifier

tokens_spec: TOKENS id_list? RBRACE
channels_spec: CHANNELS id_list? RBRACE
id_list: identifier (COMMA identifier)* COMMA?
action_: AT (action_scope_name COLONCOLON)? identifier action_block

action_scope_name \
   : identifier
   | LEXER
   | PARSER


ACTION_BLOCK: LBRACE /[^}]*/ RBRACE

action_block: ACTION_BLOCK

ARG_ACTION_BLOCK: LBRACK /[^\]]/ RBRACK

arg_action_block: ARG_ACTION_BLOCK

ARGUMENT_CONTENT: /./

END_ARGUMENT: RBRACK
RBRACK: "]"

mode_spec: MODE identifier SEMI lexer_rule_spec*

rules: rule_spec*

rule_spec \
   : parser_rule_spec
   | lexer_rule_spec

parser_rule_spec: \
   rule_modifiers? \
   RULE_REF \
   arg_action_block? \
   rule_returns? \
   throws_spec? \
   locals_spec? \
   rule_prequel* \
   COLON \
   rule_block \
   SEMI \
   exception_group

exception_group: exception_handler* finally_clause?

exception_handler: CATCH arg_action_block action_block

finally_clause: FINALLY action_block

rule_prequel \
   : options_spec
   | rule_action

rule_returns \
   : RETURNS arg_action_block

throws_spec: THROWS identifier (COMMA identifier)*

locals_spec: LOCALS arg_action_block

rule_action: AT identifier action_block

rule_modifiers: rule_modifier+

rule_modifier \
   : PUBLIC
   | PRIVATE
   | PROTECTED
   | FRAGMENT

rule_block: rule_alt_list

rule_alt_list: labeled_alt (OR labeled_alt)*

labeled_alt: alternative (POUND identifier)?

lexer_rule_spec: FRAGMENT? TOKEN_REF options_spec? COLON lexer_rule_block SEMI

lexer_rule_block: lexer_alt_list

lexer_alt_list: lexer_alt (OR lexer_alt)*

lexer_alt \
    : lexer_elements lexer_commands?
    |

lexer_elements \
   : lexer_element+
   |

lexer_element \
   : labeled_lexer_element ebnf_suffix?
   | lexer_atom ebnf_suffix?
   | lexer_block ebnf_suffix?
   | opt_action_block
   | action_block

opt_action_block: action_block QUESTION

labeled_lexer_element \
   : identifier (ASSIGN | PLUS_ASSIGN) (lexer_atom | lexer_block)

lexer_block: LPAREN lexer_alt_list RPAREN

lexer_commands: RARROW lexer_command (COMMA lexer_command)*

lexer_command \
   : lexer_command_name LPAREN lexer_command_expr RPAREN
   | lexer_command_name

lexer_command_name: identifier | MODE

lexer_command_expr: identifier | INT

alt_list: alternative (OR alternative)*

alternative \
   : element_options? element+
   |

element \
   : labeled_element ebnf_suffix?
   | atom ebnf_suffix?
   | block block_suffix?
   | action_block
   | opt_action_block

labeled_element: identifier (ASSIGN | PLUS_ASSIGN) (atom | block)

block_suffix: ebnf_suffix

ebnf_suffix \
   : QUESTION QUESTION?
   | STAR QUESTION?
   | PLUS QUESTION?

lexer_char_set: LEXER_CHAR_SET

lexer_atom \
   : character_range
   | terminal
   | not_set
   | lexer_char_set
   | any_char element_options?

any_char: DOT

LEXER_CHAR_SET: LBRACK ( /[^\]\\]/ | ESCANY )+ RBRACK

atom \
   : terminal
   | ruleref
   | not_set
   | any_char element_options?

not_set \
   : NOT set_element
   | NOT block_set

block_set: LPAREN set_element (OR set_element)* RPAREN

set_element \
   : TOKEN_REF element_options?
   | STRING_LITERAL element_options?
   | character_range
   | lexer_char_set

block: LPAREN (options_spec? rule_action* COLON)? alt_list RPAREN

ruleref: RULE_REF arg_action_block? element_options?

RULE_REF: /[a-z][a-zA-Z_0-9]*/
TOKEN_REF: /[A-Z][a-zA-Z_0-9]*/

character_range: STRING_LITERAL RANGE STRING_LITERAL

terminal \
   : TOKEN_REF element_options?
   | STRING_LITERAL element_options?

element_options: LT element_option (COMMA element_option)* GT

element_option \
   : identifier
   | identifier ASSIGN (identifier | STRING_LITERAL)

identifier \
   : RULE_REF
   | TOKEN_REF

"""

parser = Lark(grammar, start = "grammar_spec", lexer = "basic")

antlr_4_grammar = grammar
antlr_4_parser = parser
