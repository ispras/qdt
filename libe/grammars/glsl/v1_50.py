__all__ = [
    "glsl_1_50_grammar",
    "glsl_1_50_parser",
]

# sudo python -m pip install lark
from lark import (
    Lark,
)

# Based (but not just copied) on:
# https://registry.khronos.org/OpenGL/specs/gl/GLSLangSpec.1.50.pdf
grammar = """
%import common.DIGIT
%import common.HEXDIGIT
%import common.CNAME
%import common.WS
%import common.FLOAT
%ignore WS

NDIGIT: "1" .. "9"

INT_SFX: "u" | "U"

INT_CONST: ( DEC_CONST | OCT_CONST | HEX_CONST ) INT_SFX?

DEC_CONST: NDIGIT DIGIT*

OCTDIGIT: "0" .. "7"

OCT_CONST: "0" OCTDIGIT*

HEX_CONST: ( "0x" | "0X" ) HEXDIGIT+

FLOAT_SFX: "f" | "F"

FLOAT_CONST: FLOAT FLOAT_SFX?

variable_identifier: CNAME

BOOL_CONST: "true" | "false"

VOID: "void"

literal: INT_CONST | FLOAT_CONST | BOOL_CONST

?primary_expression \
    : variable_identifier
    | literal
    | "(" expression ")"

field_selection: "." CNAME

element_selection: "[" expression "]"

postfix_operator \
    : field_selection
    | "++" | "--"
    | element_selection

?postfix_expression \
    : primary_expression
    | function_call
    | postfix_expression postfix_operator

function_call: function_call_or_method

function_call_or_method \
    : function_call_generic
    | postfix_expression "." function_call_generic

?function_call_generic \
    : function_call_header_with_parameters ")"
    | function_call_header_no_parameters ")"

?function_call_header_no_parameters \
    : function_call_header VOID
    | function_call_header

?function_call_header_with_parameters \
    : function_call_header assignment_expression
    | function_call_header_with_parameters "," assignment_expression

?function_call_header: function_identifier "("

function_identifier \
    : type_specifier
    | CNAME

?unary_expression \
    : postfix_expression
    | unary_operator unary_expression

unary_operator: "+" | "-" | "!" | "~" | "++" | "--"

?multiplicative_expression \
    : unary_expression
    | multiplicative_expression "*" unary_expression
    | multiplicative_expression "/" unary_expression
    | multiplicative_expression "%" unary_expression

?additive_expression \
    : multiplicative_expression
    | additive_expression "+" multiplicative_expression
    | additive_expression "-" multiplicative_expression

?shift_expression \
    : additive_expression
    | shift_expression "<<" additive_expression
    | shift_expression ">>" additive_expression

?relational_expression \
    : shift_expression
    | relational_expression "<" shift_expression
    | relational_expression ">" shift_expression
    | relational_expression "<=" shift_expression
    | relational_expression ">=" shift_expression

?equality_expression \
    : relational_expression
    | equality_expression "==" relational_expression
    | equality_expression "!=" relational_expression

?and_expression \
    : equality_expression
    | and_expression "&" equality_expression

?exclusive_or_expression \
    : and_expression
    | exclusive_or_expression "^" and_expression

?inclusive_or_expression \
    : exclusive_or_expression
    | inclusive_or_expression "|" exclusive_or_expression

?logical_and_expression \
    : inclusive_or_expression
    | logical_and_expression "&&" inclusive_or_expression

?logical_xor_expression \
    : logical_and_expression
    | logical_xor_expression "^^" logical_and_expression

?logical_or_expression \
    : logical_xor_expression
    | logical_or_expression "||" logical_xor_expression

?conditional_expression \
    : logical_or_expression
    | logical_or_expression "?" expression ":" assignment_expression

?assignment_expression \
    : conditional_expression
    | unary_expression assignment_operator assignment_expression

assignment_operator \
    : "="
    | "*=" | "/=" | "%="
    | "+=" | "-="
    | "<<=" | ">>="
    | "&=" | "^=" | "|="

?expression \
    : assignment_expression
    | expression "," assignment_expression

constant_expression: conditional_expression

struct_declaration \
    : type_qualifiers CNAME "{" struct_field_list "}"
    | type_qualifiers CNAME "{" struct_field_list "}" CNAME

struct_array_declaration \
    : struct_declaration "[" "]"
    | struct_declaration "[" constant_expression "]"

precision_declaration: "precision" type_specifier_prec

declarations \
    : function_prototype ";"
    | init_declarator_list ";"
    | precision_declaration ";"
    | struct_declaration ";"
    | struct_array_declaration ";"
    | type_qualifiers ";"

function_prototype: function_declarator ")"

function_declarator \
    : function_header
    | function_header_with_parameters

function_header_with_parameters \
    : function_header parameter_declaration
    | function_header_with_parameters "," parameter_declaration

function_header: fully_specified_type CNAME "("

parameter_declarator \
    : type_specifier CNAME
    | type_specifier CNAME "[" constant_expression "]"

parameter_declaration \
    : parameter_type_qualifier parameter_qualifier parameter_declarator
    | parameter_qualifier parameter_declarator
    | parameter_type_qualifier parameter_qualifier parameter_type_specifier
    | parameter_qualifier parameter_type_specifier

parameter_qualifier: [ "in" | "out" | "inout" ]

parameter_type_specifier: type_specifier

?init_declarator_list \
    : single_declaration
    | init_declarator_list "," CNAME
    | init_declarator_list "," CNAME "[" "]"
    | init_declarator_list "," CNAME "[" constant_expression "]"
    | init_declarator_list "," CNAME "[" "]" "=" initializer
    | init_declarator_list "," CNAME "[" constant_expression "]" \
        "=" initializer
    | init_declarator_list "," CNAME "=" initializer

scalar_declaration: fully_specified_type CNAME [ "=" initializer ]

array_declaration \
    : scalar_declaration "[" constant_expression? "]" [ "=" initializer ]

type_declaration: fully_specified_type | "invariant" CNAME

?single_declaration \
    : type_declaration
    | scalar_declaration
    | array_declaration

fully_specified_type \
    : type_specifier
    | type_qualifiers type_specifier

invariant_qualifier: "invariant"

interpolation_qualifier: "smooth" | "flat" | "noperspective"

layout_qualifier: "layout" "(" layout_qualifier_id_list ")"

?layout_qualifier_id_list \
    : layout_qualifier_id
    | layout_qualifier_id_list "," layout_qualifier_id

layout_qualifier_id \
    : CNAME
    | CNAME "=" INT_CONST

parameter_type_qualifier: "const"

type_qualifiers \
    : storage_qualifier
    | layout_qualifier
    | layout_qualifier storage_qualifier
    | interpolation_qualifier storage_qualifier
    | interpolation_qualifier
    | invariant_qualifier storage_qualifier
    | invariant_qualifier interpolation_qualifier storage_qualifier

storage_qualifier \
    : "const"
    | "attribute"
    | "centroid" ? "varying"
    | "centroid" ? [ "in" | "out" ]
    | "uniform" -> uniform

type_specifier_prec: precision_qualifier type_specifier_no_prec

type_specifier \
    : type_specifier_no_prec
    | type_specifier_prec

?type_specifier_no_prec \
    : type_specifier_nonarray
    | type_specifier_array

type_specifier_array: type_specifier_nonarray "[" constant_expression? "]"

type_specifier_nonarray \
    : struct_specifier
    | CNAME
    | VOID

precision_qualifier \
    : "highp"
    | "mediump"
    | "lowp"

struct_specifier \
    : "struct" CNAME "{" struct_field_list "}"
    | "struct" "{" struct_field_list "}"

?struct_field_list \
    : field_declaration
    | struct_field_list field_declaration

field_declaration \
    : type_specifier field_declarator_list ";"
    | type_qualifiers type_specifier field_declarator_list ";"

?field_declarator_list \
    : field_declarator
    | field_declarator_list "," field_declarator

field_declarator \
    : CNAME
    | CNAME "[" "]"
    | CNAME "[" constant_expression "]"

initializer: assignment_expression

declarations_statement: declarations

?statement \
    : compound_statement
    | simple_statement

?simple_statement \
    : declarations_statement
    | expression_statement
    | selection_statement
    | switch_statement
    | case_label
    | iteration_statement
    | jump_statement

compound_statement \
    : "{" "}"
    | "{" statement_list "}"

statement_no_new_scope \
    : compound_statement_no_new_scope
    | simple_statement

compound_statement_no_new_scope \
    : "{" "}"
    | "{" statement_list "}"

?statement_list \
    : statement
    | statement_list statement

?expression_statement: expression? ";"

selection_statement: "if" "(" expression ")" selection_rest_statement

selection_rest_statement \
    : statement "else" statement
    | statement

condition \
    : expression
    | fully_specified_type CNAME "=" initializer

switch_statement \
    : "switch" "(" expression ")" "{" switch_statement_list "}"

switch_statement_list: statement_list?

case_label \
    : "case" expression ":"
    | "default" ":"

iteration_statement \
    : "while" "(" condition ")" statement_no_new_scope
    | "do" statement "while" "(" expression ")" ";"
    | "for" "(" for_init_statement for_rest_statement ")" \
        statement_no_new_scope

for_init_statement \
    : expression_statement
    | declarations_statement

conditionopt: condition

for_rest_statement: conditionopt? ";" expression?

jump_statement \
    : "continue" ";"
    | "break" ";"
    | "return" ";"
    | "return" expression ";"
    | "discard" ";"

translation_unit: (function_definition | toplevel_declarations)+

toplevel_declarations: declarations

function_definition: function_prototype compound_statement_no_new_scope
"""

parser = Lark(grammar, start = "translation_unit", lexer = "basic")

glsl_1_50_grammar = grammar
glsl_1_50_parser = parser
