#!/usr/bin/env python3

from argparse import (
    ArgumentParser,
)
from codecs import (
    BOM_UTF8,
    decode,
)
from itertools import (
    zip_longest,
)
from os import (
    makedirs,
    walk,
)
from os.path import (
    isdir,
    join,
)
from re import (
    compile,
    MULTILINE,
    UNICODE,
    VERBOSE,
)
from time import (
    time,
)
from traceback import (
    print_exc,
)

# based on
# https://github.com/mesonbuild/meson/blob/master/mesonbuild/mparser.py
# and other referenced files.


# This is the regex for the supported escape sequences of a regular string
# literal, like 'abc\x00'
ESCAPE_SEQUENCE_SINGLE_RE = compile(r"""
    ( \\U[A-Fa-f0-9]{8}   # 8-digit hex escapes
    | \\u[A-Fa-f0-9]{4}   # 4-digit hex escapes
    | \\x[A-Fa-f0-9]{2}   # 2-digit hex escapes
    | \\[0-7]{1,3}        # Octal escapes
    | \\N\{[^}]+\}        # Unicode characters by name
    | \\[\\'abfnrtv]      # Single-character escapes
    )""",
    UNICODE | VERBOSE
)


def decode_match(m):
    return decode(m.group(0).encode(), "unicode_escape")


class MesonException(Exception):
    "Exceptions thrown by Meson"

    def __init__(self, *args,
        file = None,
        lineno = None,
        colno = None,
    ):
        super().__init__(*args)
        self.file = file
        self.lineno = lineno
        self.colno = colno


def code_line(text, line, colno):
    """Print a line with a caret pointing to the colno

:param text: A message to display before the line
:param line: The line of code to be pointed to
:param colno: The column number to point at
:return: A formatted string of the text, line, and a caret
    """
    return f"{text}\n{line}\n{' ' * colno}^"


def warning(msg, **__):
    print(msg)


class ParseException(MesonException):

    ast = None

    def __init__(self, text, line, lineno, colno):
        # Format as error message, followed by the line with the error,
        # followed by a caret to show the error column.
        super().__init__(code_line(text, line, colno))
        self.lineno = lineno
        self.colno = colno


class BlockParseException(ParseException):

    def __init__(self, text, line, lineno, colno,
        start_line,
        start_lineno,
        start_colno,
    ):
        # This can be formatted in two ways --- one if the block start and
        # end are on the same line, and a different way if they are on
        # different lines.

        if lineno == start_lineno:
            # If block start and end are on the same line, it is formatted as:
            # Error message
            # Followed by the line with the error
            # Followed by a caret to show the block start
            # Followed by underscores
            # Followed by a caret to show the block end.
            MesonException.__init__(self,
                "{}\n{}\n{}".format(
                    text,
                    line, "{}^{}^".format(
                        ' ' * start_colno,
                        '_' * (colno - start_colno - 1)
                    )
                )
            )
        else:
            # If block start and end are on different lines, it is formatted as:
            # Error message
            # Followed by the line with the error
            # Followed by a caret to show the error column.
            # Followed by a message saying where the block started.
            # Followed by the line of the block start.
            # Followed by a caret for the block start.
            MesonException.__init__(self,
                "%s\n%s\n%s\nFor a block that started at %d,%d\n%s\n%s" % (
                    text,
                    line,
                    "%s^" % (' ' * colno),
                    start_lineno,
                    start_colno,
                    start_line,
                    "%s^" % (' ' * start_colno)
                )
            )

        self.lineno = lineno
        self.colno = colno


class Token(object):

    def __init__(self,
        tid,
        filename,
        line_start,
        lineno,
        colno,
        bytespan,
        value,
    ):
        self.tid = tid
        self.filename = filename
        self.line_start = line_start
        self.lineno = lineno
        self.colno = colno
        self.bytespan = bytespan
        self.value = value

    def __eq__(self, other):
        if isinstance(other, str):
            return self.tid == other
        elif isinstance(other, Token):
            return self.tid == other.tid
        return NotImplemented


def matcher(expr, *a, **kw):
    return compile(expr, *a, **kw).match

TOKEN_SPECIFICATION = [
    # Need to be sorted longest to shortest.
    ("whitespace", matcher(r"[ \t]+")),
    ("multiline_fstring", matcher(r"f'''(.|\n)*?'''", MULTILINE)),
    ("fstring", matcher(r"f'([^'\\]|(\\.))*'")),
    ("id", matcher("[_a-zA-Z][_0-9a-zA-Z]*")),
    ("number", matcher(
        r"0[bB][01]+|0[oO][0-7]+|0[xX][0-9a-fA-F]+|0|[1-9]\d*")
    ),
    ("eol_cont", matcher(r"\\[ \t]*(#.*)?\n")),
    ("eol", matcher(r"\n")),
    ("multiline_string", matcher(r"'''(.|\n)*?'''", MULTILINE)),
    ("comment", matcher("#.*")),
    ("lparen", matcher("[(]")),
    ("rparen", matcher("[)]")),
    ("lbracket", matcher(r"\[")),
    ("rbracket", matcher("]")),
    ("lcurl", matcher("[{]")),
    ("rcurl", matcher("[}]")),
    ("dblquote", matcher('"')),
    ("string", matcher(r"'([^'\\]|(\\.))*'")),
    ("comma", matcher(",")),
    ("plusassign", matcher("[+]=")),
    ("dot", matcher("[.]")),
    ("plus", matcher("[+]")),
    ("dash", matcher("-")),
    ("star", matcher("[*]")),
    ("percent", matcher("%")),
    ("fslash", matcher("/")),
    ("colon", matcher(":")),
    ("equal", matcher("==")),
    ("nequal", matcher("!=")),
    ("assign", matcher("=")),
    ("le", matcher("<=")),
    ("lt", matcher("<")),
    ("ge", matcher(">=")),
    ("gt", matcher(">")),
    ("questionmark", matcher("[?]")),
]


KEYWORDS = {
    "true", "false",
    "if", "else", "elif", "endif",
    "and", "or", "not",
    "foreach", "endforeach",
    "in",
    "continue", "break",
}
FUTURE_KEYWORDS = {
    "return",
}


class Lexer:

    def __init__(self, code: str):
        if code.startswith(BOM_UTF8.decode("utf-8")):
            line, *_ = code.split('\n', maxsplit = 1)
            raise ParseException(
                "Builder file must be encoded in UTF-8 (with no BOM)",
                line,
                lineno = 0,
                colno = 0
            )

        self.code = code

    def getline(self, line_start):
        return self.code[ line_start : self.code.find('\n', line_start) ]

    def lex(self, filename):
        line_start = 0
        lineno = 1
        loc = 0
        par_count = 0
        bracket_count = 0
        curl_count = 0
        col = 0
        while loc < len(self.code):
            for (tid, matcher) in TOKEN_SPECIFICATION:
                mo = matcher(self.code, loc)
                if not mo:
                    continue
                curline = lineno
                curline_start = line_start
                col = mo.start() - line_start
                span_start = loc
                loc = mo.end()
                span_end = loc
                bytespan = (span_start, span_end)
                value = mo.group()
                if tid == "lparen":
                    par_count += 1
                elif tid == "rparen":
                    par_count -= 1
                elif tid == "lbracket":
                    bracket_count += 1
                elif tid == "rbracket":
                    bracket_count -= 1
                elif tid == "lcurl":
                    curl_count += 1
                elif tid == "rcurl":
                    curl_count -= 1
                elif tid == "dblquote":
                    raise ParseException(
                        "Double quotes are not supported. Use single quotes.",
                        self.getline(line_start),
                        lineno,
                        col
                    )
                elif tid in {"string", "fstring"}:
                    if value.find("\n") != -1:
                        msg = (
"Newline character in a string detected, use ''' (three single quotes)"
" for multiline strings instead.\n"
"This will become a hard error in a future Meson release.")
                        warning(code_line(msg, self.getline(line_start), col),
                            location = BaseNode(lineno, col, filename)
                        )
                    value = value[ (2 if tid == "fstring" else 1) : -1 ]
                elif tid in {"multiline_string", "multiline_fstring"}:
                    value = value[
                        (4 if tid == "multiline_fstring" else 3) : -3
                    ]
                    lines = value.split('\n')
                    if len(lines) > 1:
                        lineno += len(lines) - 1
                        line_start = mo.end() - len(lines[-1])
                elif tid == "eol_cont":
                    lineno += 1
                    line_start = loc
                    tid = "whitespace"
                elif tid == "eol":
                    lineno += 1
                    line_start = loc
                    if par_count > 0 or bracket_count > 0 or curl_count > 0:
                        tid = "whitespace"
                elif tid == "id":
                    if value in KEYWORDS:
                        tid = value
                    else:
                        if value in FUTURE_KEYWORDS:
                            warning((
f"Identifier '{value}' will become a reserved keyword in a future release."
f" Please rename it."
                                ),
                                location = BaseNode(lineno, col, filename)
                            )
                yield Token(
                    tid, filename, curline_start, curline, col, bytespan, value
                )
                break
            else:
                raise ParseException(
                    "lexer", self.getline(line_start), lineno, col
                )


class BaseNode:

    def __init__(self, lineno, colno, filename,
        end_lineno = None,
        end_colno = None,
    ):
        self.lineno = lineno
        self.colno = colno
        self.filename = filename
        self.end_lineno = end_lineno if end_lineno is not None else lineno
        self.end_colno = end_colno if end_colno is not None else colno
        self.whitespaces = None

        # Attributes for the visitors
        self.level = 0
        self.ast_id = ''
        self.condition_level = 0

    def accept(self, visitor):
        for pfx in (
            "enter_",
            "visit_",
            "exit_",
        ):
            for sfx in [type(self).__name__, "node"]:
                func = getattr(visitor, pfx + sfx, None)
                if func is not None:
                    func(self)
                    break

    def append_whitespaces(self, token):
        if self.whitespaces is None:
            self.whitespaces = WhitespaceNode(token)
        else:
            self.whitespaces.append(token)


class WhitespaceNode(BaseNode):

    def __init__(self, token):
        super().__init__(token.lineno, token.colno, token.filename)
        self.value = ""
        self.append(token)
        self.block_indent = False
        self.is_continuation = False

    def append(self, token):
        self.value += token.value


class ElementaryNode(BaseNode):

    def __init__(self, token):
        super().__init__(token.lineno, token.colno, token.filename)
        self.value = token.value
        self.bytespan = token.bytespan


class BooleanNode(ElementaryNode):
    pass


class IdNode(ElementaryNode):
    pass


class NumberNode(ElementaryNode):

    def __init__(self, token):
        BaseNode.__init__(self, token.lineno, token.colno, token.filename)
        self.raw_value = token.value
        self.value = int(token.value, base = 0)
        self.bytespan = token.bytespan


class StringNode(ElementaryNode):

    def __init__(self, token, escape = True):
        super().__init__(token)

        self.is_multiline = "multiline" in token.tid
        self.is_fstring = "fstring" in token.tid
        self.raw_value = token.value

        if escape and not self.is_multiline:
            self.value = self.escape()

    def escape(self):
        return ESCAPE_SEQUENCE_SINGLE_RE.sub(decode_match, self.raw_value)


class ContinueNode(ElementaryNode):
    pass


class BreakNode(ElementaryNode):
    pass


class SymbolNode(ElementaryNode):
    pass


class ArgumentNode(BaseNode):

    def __init__(self, token):
        super().__init__(token.lineno, token.colno, token.filename)
        self.arguments = []
        self.commas = []
        self.colons = []
        self.kwargs = {}
        self.order_error = False

        # Attributes for the visitors
        self.is_multiline = False

    def prepend(self, statement):
        if self.num_kwargs() > 0:
            self.order_error = True
        if not isinstance(statement, EmptyNode):
            self.arguments = [statement] + self.arguments

    def append(self, statement):
        if self.num_kwargs() > 0:
            self.order_error = True
        if not isinstance(statement, EmptyNode):
            self.arguments += [statement]

    def set_kwarg(self, name, value):
        if any((isinstance(x, IdNode) and name.value == x.value) for x in self.kwargs):
            warning(
                f'Keyword argument "{name.value}" defined multiple times.',
                location = self
            )
            warning("This will be an error in Meson 2.0.")
        self.kwargs[name] = value

    def set_kwarg_no_check(self, name, value):
        self.kwargs[name] = value

    def num_args(self):
        return len(self.arguments)

    def num_kwargs(self):
        return len(self.kwargs)

    def incorrect_order(self):
        return self.order_error

    def __len__(self):
        return self.num_args() + self.num_kwargs()


class ArrayNode(BaseNode):

    def __init__(self, lbracket, args, rbracket):
        super().__init__(
            lbracket.lineno,
            lbracket.colno,
            args.filename,
            end_lineno = rbracket.lineno,
            end_colno = rbracket.colno + 1,
        )
        self.lbracket = lbracket
        self.args = args
        self.rbracket = rbracket


class DictNode(BaseNode):

    def __init__(self,
        lcurl: SymbolNode,
        args: ArgumentNode,
        rcurl: SymbolNode,
    ):
        super().__init__(lcurl.lineno, lcurl.colno, args.filename,
            end_lineno = rcurl.lineno,
            end_colno = rcurl.colno + 1,
        )
        self.lcurl = lcurl
        self.args = args
        self.rcurl = rcurl


class EmptyNode(BaseNode):
    pass


class BinaryOperatorNode(BaseNode):

    def __init__(self, left, operator, right):
        super().__init__(left.lineno, left.colno, left.filename)
        self.left = left
        self.operator = operator
        self.right = right


class OrNode(BinaryOperatorNode):
    pass


class AndNode(BinaryOperatorNode):
    pass


class ComparisonNode(BinaryOperatorNode):

    def __init__(self, ctype, left, operator, right):
        super().__init__(left, operator, right)
        self.ctype = ctype


class ArithmeticNode(BinaryOperatorNode):

    # TODO: use a Literal for operation
    def __init__(self, operation, left, operator, right):
        super().__init__(left, operator, right)
        self.operation = operation


class UnaryOperatorNode(BaseNode):

    def __init__(self, token, operator, value):
        super().__init__(token.lineno, token.colno, token.filename)
        self.operator = operator
        self.value = value


class NotNode(UnaryOperatorNode):
    pass


class UMinusNode(UnaryOperatorNode):
    pass


class CodeBlockNode(BaseNode):

    def __init__(self, token):
        super().__init__(token.lineno, token.colno, token.filename)
        self.pre_whitespaces = None
        self.lines = []

    def append_whitespaces(self, token):
        if self.lines:
            self.lines[-1].append_whitespaces(token)
        elif self.pre_whitespaces is None:
            self.pre_whitespaces = WhitespaceNode(token)
        else:
            self.pre_whitespaces.append(token)


class IndexNode(BaseNode):

    def __init__(self, iobject, lbracket, index, rbracket):
        super().__init__(iobject.lineno, iobject.colno, iobject.filename)
        self.iobject = iobject
        self.lbracket = lbracket
        self.index = index
        self.rbracket = rbracket


class MethodNode(BaseNode):

    def __init__(self, source_object, dot, name, lpar, args, rpar):
        super().__init__(name.lineno, name.colno, name.filename,
            end_lineno = rpar.lineno,
            end_colno = rpar.colno + 1,
        )
        self.source_object = source_object
        self.dot = dot
        self.name = name
        self.lpar = lpar
        self.args = args
        self.rpar = rpar


class FunctionNode(BaseNode):

    def __init__(self, func_name, lpar, args, rpar):
        super().__init__(func_name.lineno, func_name.colno, func_name.filename,
            end_lineno = rpar.end_lineno,
            end_colno = rpar.end_colno + 1,
        )
        self.func_name = func_name
        self.lpar = lpar
        self.args = args
        self.rpar = rpar

class AssignmentNode(BaseNode):

    def __init__(self, var_name, operator, value):
        super().__init__(var_name.lineno, var_name.colno, var_name.filename)
        self.var_name = var_name
        self.operator = operator
        self.value = value


class PlusAssignmentNode(AssignmentNode):
    pass


class ForeachClauseNode(BaseNode):

    def __init__(self, foreach_, varnames, commas, colon, items, block,
        endforeach
    ):
        super().__init__(foreach_.lineno, foreach_.colno, foreach_.filename)
        self.foreach_ = foreach_
        self.varnames = varnames
        self.commas = commas
        self.colon = colon
        self.items = items
        self.block = block
        self.endforeach = endforeach


class IfNode(BaseNode):

    def __init__(self, linenode, if_node, condition, block):
        super().__init__(linenode.lineno, linenode.colno, linenode.filename)
        self.if_ = if_node
        self.condition = condition
        self.block = block


class ElseNode(BaseNode):

    def __init__(self, else_, block):
        super().__init__(block.lineno, block.colno, block.filename)
        self.else_ = else_
        self.block = block


class IfClauseNode(BaseNode):

    def __init__(self, linenode):
        super().__init__(linenode.lineno, linenode.colno, linenode.filename)
        self.ifs = []
        self.elseblock = EmptyNode(
            linenode.lineno, linenode.colno, linenode.filename
        )


class TestCaseClauseNode(BaseNode):

    def __init__(self, testcase, condition, block, endtestcase):
        super().__init__(condition.lineno, condition.colno, condition.filename)
        self.testcase = testcase
        self.condition = condition
        self.block = block
        self.endtestcase = endtestcase


class TernaryNode(BaseNode):

    def __init__(self, condition, questionmark, trueblock, colon, falseblock):
        super().__init__(condition.lineno, condition.colno, condition.filename)
        self.condition = condition
        self.questionmark = questionmark
        self.trueblock = trueblock
        self.colon = colon
        self.falseblock = falseblock


comparison_map = {
    "equal": "==",
    "nequal": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
    "in": "in",
    "not in": "notin",
}


class ParenthesizedNode(BaseNode):

    def __init__(self, lpar, inner, rpar):
        super().__init__(lpar.lineno, lpar.colno, inner.filename,
            end_lineno = rpar.lineno,
            end_colno = rpar.colno + 1,
        )
        self.lpar = lpar
        self.inner = inner
        self.rpar = rpar


# Recursive descent parser for Meson's definition language.
# Very basic apart from the fact that we have many precedence
# levels so there are not enough words to describe them all.
# Enter numbering:
#
# 1 assignment
# 2 or
# 3 and
# 4 comparison
# 5 arithmetic
# 6 negation
# 7 funcall, method call
# 8 parentheses
# 9 plain token


class Parser:

    def __init__(self, code, filename):
        self.lexer = Lexer(code)
        self.stream = self.lexer.lex(filename)
        self.current = Token("eof", '', 0, 0, 0, (0, 0), None)
        self.previous = self.current
        self.current_ws = []

        self.getsym()
        self.in_ternary = False

    def create_node(self, node_type, *args, **kwargs):
        node = node_type(*args, **kwargs)
        for ws_token in self.current_ws:
            node.append_whitespaces(ws_token)
        self.current_ws = []
        return node

    def getsym(self):
        self.previous = self.current
        try:
            self.current = next(self.stream)

            while self.current.tid in {"eol", "comment", "whitespace"}:
                self.current_ws.append(self.current)
                if self.current.tid == "eol":
                    break
                self.current = next(self.stream)

        except StopIteration:
            self.current = Token(
                "eof",
                '',
                self.current.line_start,
                self.current.lineno,
                self.current.colno
                  + self.current.bytespan[1]
                  - self.current.bytespan[0]
                ,
                (0, 0),
                None,
            )

    def getline(self):
        return self.lexer.getline(self.current.line_start)

    def accept(self, s):
        if self.current.tid == s:
            self.getsym()
            return True
        return False

    def accept_any(self, tids):
        tid = self.current.tid
        if tid in tids:
            self.getsym()
            return tid
        return ''

    def expect(self, s):
        if self.accept(s):
            return True
        raise ParseException(
            f"Expecting {s} got {self.current.tid}.",
            self.getline(),
            self.current.lineno,
            self.current.colno,
        )

    def block_expect(self, s, block_start):
        if self.accept(s):
            return True
        raise BlockParseException(
            f"Expecting {s} got {self.current.tid}.",
            self.getline(),
            self.current.lineno,
            self.current.colno,
            self.lexer.getline(block_start.line_start),
            block_start.lineno,
            block_start.colno,
        )

    def parse(self):
        block = self.codeblock()
        try:
            self.expect("eof")
        except ParseException as e:
            e.ast = block
            raise
        return block

    def statement(self):
        return self.e1()

    def e1(self):
        left = self.e2()
        if self.accept("plusassign"):
            operator = self.create_node(SymbolNode, self.previous)
            value = self.e1()
            if not isinstance(left, IdNode):
                raise ParseException(
                    "Plusassignment target must be an id.",
                    self.getline(), left.lineno, left.colno,
                )
            return self.create_node(PlusAssignmentNode, left, operator, value)
        elif self.accept("assign"):
            operator = self.create_node(SymbolNode, self.previous)
            value = self.e1()
            if not isinstance(left, IdNode):
                raise ParseException(
                    "Assignment target must be an id.",
                    self.getline(), left.lineno, left.colno,
                )
            return self.create_node(AssignmentNode, left, operator, value)
        elif self.accept("questionmark"):
            if self.in_ternary:
                raise ParseException(
                    "Nested ternary operators are not allowed.",
                    self.getline(), left.lineno, left.colno,
                )

            qm_node = self.create_node(SymbolNode, self.previous)
            self.in_ternary = True
            trueblock = self.e1()
            self.expect("colon")
            colon_node = self.create_node(SymbolNode, self.previous)
            falseblock = self.e1()
            self.in_ternary = False
            return self.create_node(
                TernaryNode, left, qm_node, trueblock, colon_node, falseblock,
            )
        return left

    def e2(self):
        left = self.e3()
        while self.accept("or"):
            operator = self.create_node(SymbolNode, self.previous)
            if isinstance(left, EmptyNode):
                raise ParseException(
                    "Invalid or clause.",
                    self.getline(), left.lineno, left.colno,
                )
            left = self.create_node(OrNode, left, operator, self.e3())
        return left

    def e3(self):
        left = self.e4()
        while self.accept("and"):
            operator = self.create_node(SymbolNode, self.previous)
            if isinstance(left, EmptyNode):
                raise ParseException(
                    "Invalid and clause.",
                    self.getline(), left.lineno, left.colno,
                )
            left = self.create_node(AndNode, left, operator, self.e4())
        return left

    def e4(self):
        left = self.e5()
        for nodename, operator_type in comparison_map.items():
            if self.accept(nodename):
                operator = self.create_node(SymbolNode, self.previous)
                return self.create_node(
                    ComparisonNode, operator_type, left, operator, self.e5(),
                )
        if self.accept("not"):
            ws = self.current_ws.copy()
            not_token = self.previous
            if self.accept("in"):
                in_token = self.previous
                # remove whitespaces between not and in
                self.current_ws = self.current_ws[len(ws):]
                temp_node = EmptyNode(
                    in_token.lineno, in_token.colno, in_token.filename,
                )
                for w in ws:
                    temp_node.append_whitespaces(w)

                not_token.bytespan = (
                    not_token.bytespan[0], in_token.bytespan[1]
                )
                not_token.value += temp_node.whitespaces.value + in_token.value
                operator = self.create_node(SymbolNode, not_token)
                return self.create_node(
                    ComparisonNode, "notin", left, operator, self.e5(),
                )
        return left

    def e5(self):
        return self.e5addsub()

    def e5addsub(self):
        op_map = {
            "plus": "add",
            "dash": "sub",
        }
        left = self.e5muldiv()
        while True:
            op = self.accept_any(tuple(op_map.keys()))
            if op:
                operator = self.create_node(SymbolNode, self.previous)
                left = self.create_node(
                    ArithmeticNode, op_map[op], left, operator,
                    self.e5muldiv(),
                )
            else:
                break
        return left

    def e5muldiv(self):
        op_map = {
            "percent": "mod",
            "star": "mul",
            "fslash": "div",
        }
        left = self.e6()
        while True:
            op = self.accept_any(tuple(op_map.keys()))
            if op:
                operator = self.create_node(SymbolNode, self.previous)
                left = self.create_node(
                    ArithmeticNode, op_map[op], left, operator, self.e6(),
                )
            else:
                break
        return left

    def e6(self):
        if self.accept("not"):
            operator = self.create_node(SymbolNode, self.previous)
            return self.create_node(NotNode, self.current, operator, self.e7())
        if self.accept("dash"):
            operator = self.create_node(SymbolNode, self.previous)
            return self.create_node(
                UMinusNode, self.current, operator, self.e7(),
            )
        return self.e7()

    def e7(self):
        left = self.e8()
        block_start = self.current
        if self.accept("lparen"):
            lpar = self.create_node(SymbolNode, block_start)
            args = self.args()
            self.block_expect("rparen", block_start)
            rpar = self.create_node(SymbolNode, self.previous)
            if not isinstance(left, IdNode):
                raise ParseException(
                    "Function call must be applied to plain id",
                    self.getline(), left.lineno, left.colno,
                )
            assert isinstance(left.value, str)
            left = self.create_node(FunctionNode, left, lpar, args, rpar)
        go_again = True
        while go_again:
            go_again = False
            if self.accept("dot"):
                go_again = True
                left = self.method_call(left)
            if self.accept("lbracket"):
                go_again = True
                left = self.index_call(left)
        return left

    def e8(self):
        block_start = self.current
        if self.accept("lparen"):
            lpar = self.create_node(SymbolNode, block_start)
            e = self.statement()
            self.block_expect("rparen", block_start)
            rpar = self.create_node(SymbolNode, self.previous)
            return ParenthesizedNode(lpar, e, rpar)
        elif self.accept("lbracket"):
            lbracket = self.create_node(SymbolNode, block_start)
            args = self.args()
            self.block_expect("rbracket", block_start)
            rbracket = self.create_node(SymbolNode, self.previous)
            return self.create_node(ArrayNode, lbracket, args, rbracket)
        elif self.accept("lcurl"):
            lcurl = self.create_node(SymbolNode, block_start)
            key_values = self.key_values()
            self.block_expect("rcurl", block_start)
            rcurl = self.create_node(SymbolNode, self.previous)
            return self.create_node(DictNode, lcurl, key_values, rcurl)
        else:
            return self.e9()

    def e9(self):
        t = self.current
        if self.accept("true"):
            t.value = True
            return self.create_node(BooleanNode, t)
        if self.accept("false"):
            t.value = False
            return self.create_node(BooleanNode, t)
        if self.accept("id"):
            return self.create_node(IdNode, t)
        if self.accept("number"):
            return self.create_node(NumberNode, t)
        if self.accept_any((
            "string", "fstring", "multiline_string", "multiline_fstring",
        )):
            return self.create_node(StringNode, t)
        return EmptyNode(
            self.current.lineno, self.current.colno, self.current.filename,
        )

    def key_values(self):
        s = self.statement()
        a = self.create_node(ArgumentNode, self.current)

        while not isinstance(s, EmptyNode):
            if self.accept("colon"):
                a.colons.append(self.create_node(SymbolNode, self.previous))
                a.set_kwarg_no_check(s, self.statement())
                if not self.accept("comma"):
                    return a
                a.commas.append(self.create_node(SymbolNode, self.previous))
            else:
                raise ParseException(
                    "Only key:value pairs are valid in dict construction.",
                    self.getline(), s.lineno, s.colno,
                )
            s = self.statement()
        return a

    def args(self):
        s = self.statement()
        a = self.create_node(ArgumentNode, self.current)

        while not isinstance(s, EmptyNode):
            if self.accept("comma"):
                a.commas.append(self.create_node(SymbolNode, self.previous))
                a.append(s)
            elif self.accept("colon"):
                a.colons.append(self.create_node(SymbolNode, self.previous))
                if not isinstance(s, IdNode):
                    raise ParseException(
                        "Dictionary key must be a plain identifier.",
                        self.getline(), s.lineno, s.colno,
                    )
                a.set_kwarg(s, self.statement())
                if not self.accept("comma"):
                    return a
                a.commas.append(self.create_node(SymbolNode, self.previous))
            else:
                a.append(s)
                return a
            s = self.statement()
        return a

    def method_call(self, source_object):
        dot = self.create_node(SymbolNode, self.previous)
        methodname = self.e9()
        if not isinstance(methodname, IdNode):
            if (
                isinstance(source_object, NumberNode)
            and isinstance(methodname, NumberNode)
            ):
                raise ParseException(
                    "meson does not support float numbers",
                    self.getline(), source_object.lineno, source_object.colno,
                )
            raise ParseException(
                "Method name must be plain id",
                self.getline(), self.current.lineno, self.current.colno,
            )

        self.expect("lparen")
        lpar = self.create_node(SymbolNode, self.previous)
        args = self.args()
        rpar = self.create_node(SymbolNode, self.current)
        self.expect("rparen")
        method = self.create_node(
            MethodNode, source_object, dot, methodname, lpar, args, rpar,
        )
        if self.accept("dot"):
            return self.method_call(method)
        return method

    def index_call(self, source_object):
        lbracket = self.create_node(SymbolNode, self.previous)
        index_statement = self.statement()
        self.expect("rbracket")
        rbracket = self.create_node(SymbolNode, self.previous)
        return self.create_node(
            IndexNode, source_object, lbracket, index_statement, rbracket,
        )

    def foreachblock(self):
        foreach_ = self.create_node(SymbolNode, self.previous)
        self.expect("id")
        assert isinstance(self.previous.value, str)
        varnames = [self.create_node(IdNode, self.previous)]
        commas = []

        if self.accept("comma"):
            commas.append(self.create_node(SymbolNode, self.previous))
            self.expect("id")
            assert isinstance(self.previous.value, str)
            varnames.append(self.create_node(IdNode, self.previous))

        self.expect("colon")
        colon = self.create_node(SymbolNode, self.previous)
        items = self.statement()
        block = self.codeblock()
        endforeach = self.create_node(SymbolNode, self.current)
        return self.create_node(
            ForeachClauseNode,
            foreach_, varnames, commas, colon, items, block, endforeach,
        )

    def ifblock(self):
        if_node = self.create_node(SymbolNode, self.previous)
        condition = self.statement()
        clause = self.create_node(IfClauseNode, condition)
        self.expect("eol")
        block = self.codeblock()
        clause.ifs.append(
            self.create_node(IfNode, clause, if_node, condition, block)
        )
        self.elseifblock(clause)
        clause.elseblock = self.elseblock()
        clause.endif = self.create_node(SymbolNode, self.current)
        return clause

    def elseifblock(self, clause):
        while self.accept("elif"):
            elif_ = self.create_node(SymbolNode, self.previous)
            s = self.statement()
            self.expect("eol")
            b = self.codeblock()
            clause.ifs.append(self.create_node(IfNode, s, elif_, s, b))

    def elseblock(self):
        if self.accept("else"):
            else_ = self.create_node(SymbolNode, self.previous)
            self.expect("eol")
            block = self.codeblock()
            return ElseNode(else_, block)
        return EmptyNode(
            self.current.lineno, self.current.colno, self.current.filename,
        )

    def testcaseblock(self):
        testcase = self.create_node(SymbolNode, self.previous)
        condition = self.statement()
        self.expect("eol")
        block = self.codeblock()
        endtestcase = SymbolNode(self.current)
        return self.create_node(
            TestCaseClauseNode, testcase, condition, block, endtestcase,
        )

    def line(self):
        block_start = self.current
        if block_start == "eol":
            return EmptyNode(
                block_start.lineno, self.current.colno, self.current.filename,
            )
        if self.accept("if"):
            ifblock = self.ifblock()
            self.block_expect("endif", block_start)
            return ifblock
        if self.accept("foreach"):
            forblock = self.foreachblock()
            self.block_expect("endforeach", block_start)
            return forblock
        if self.accept("continue"):
            return self.create_node(ContinueNode, block_start)
        if self.accept("break"):
            return self.create_node(BreakNode, block_start)
        return self.statement()

    def codeblock(self):
        block = self.create_node(CodeBlockNode, self.current)
        cond = True

        try:
            while cond:
                for ws_token in self.current_ws:
                    block.append_whitespaces(ws_token)
                self.current_ws = []

                curline = self.line()

                if not isinstance(curline, EmptyNode):
                    block.lines.append(curline)

                cond = self.accept("eol")

        except ParseException as e:
            e.ast = block
            raise

        # Remaining whitespaces will not be caught since there
        # are no more nodes
        for ws_token in self.current_ws:
            block.append_whitespaces(ws_token)
        self.current_ws = []

        return block


class AstVisitor:

    def visit_ArrayNode(self, node):
        node.args.accept(self)

    def visit_DictNode(self, node):
        node.args.accept(self)

    def visit_OrNode(self, node):
        node.left.accept(self)
        node.right.accept(self)

    def visit_AndNode(self, node):
        node.left.accept(self)
        node.right.accept(self)

    def visit_ComparisonNode(self, node):
        node.left.accept(self)
        node.right.accept(self)

    def visit_ArithmeticNode(self, node):
        node.left.accept(self)
        node.right.accept(self)

    def visit_NotNode(self, node):
        node.value.accept(self)

    def visit_CodeBlockNode(self, node):
        for i in node.lines:
            i.accept(self)

    def visit_IndexNode(self, node):
        node.iobject.accept(self)
        node.index.accept(self)

    def visit_MethodNode(self, node):
        node.source_object.accept(self)
        node.name.accept(self)
        node.args.accept(self)

    def visit_FunctionNode(self, node):
        node.func_name.accept(self)
        node.args.accept(self)

    def visit_AssignmentNode(self, node):
        self.visit_default_func(node)
        node.var_name.accept(self)
        node.value.accept(self)

    def visit_PlusAssignmentNode(self, node):
        node.var_name.accept(self)
        node.value.accept(self)

    def visit_ForeachClauseNode(self, node):
        for varname in node.varnames:
            varname.accept(self)
        node.items.accept(self)
        node.block.accept(self)

    def visit_IfClauseNode(self, node):
        for i in node.ifs:
            i.accept(self)
        node.elseblock.accept(self)

    def visit_UMinusNode(self, node):
        node.value.accept(self)

    def visit_IfNode(self, node):
        node.condition.accept(self)
        node.block.accept(self)

    def visit_ElseNode(self, node):
        node.block.accept(self)

    def visit_TernaryNode(self, node):
        node.condition.accept(self)
        node.trueblock.accept(self)
        node.falseblock.accept(self)

    def visit_ArgumentNode(self, node):
        for i in node.arguments:
            i.accept(self)
        for key, val in node.kwargs.items():
            key.accept(self)
            val.accept(self)

    def visit_ParenthesizedNode(self, node):
        node.inner.accept(self)


class FullAstVisitor(AstVisitor):
    """Visit all nodes, including Symbol and Whitespaces"""

    def exit_node(self, node):
        if node.whitespaces:
            node.whitespaces.accept(self)

    def visit_UnaryOperatorNode(self, node):
        node.operator.accept(self)
        node.value.accept(self)

    def visit_BinaryOperatorNode(self, node):
        node.left.accept(self)
        node.operator.accept(self)
        node.right.accept(self)

    def visit_ArrayNode(self, node):
        node.lbracket.accept(self)
        node.args.accept(self)
        node.rbracket.accept(self)

    def visit_DictNode(self, node):
        node.lcurl.accept(self)
        node.args.accept(self)
        node.rcurl.accept(self)

    def visit_OrNode(self, node):
        self.visit_BinaryOperatorNode(node)

    def visit_AndNode(self, node):
        self.visit_BinaryOperatorNode(node)

    def visit_ComparisonNode(self, node):
        self.visit_BinaryOperatorNode(node)

    def visit_ArithmeticNode(self, node):
        self.visit_BinaryOperatorNode(node)

    def visit_NotNode(self, node):
        self.visit_UnaryOperatorNode(node)

    def visit_CodeBlockNode(self, node):
        if node.pre_whitespaces:
            node.pre_whitespaces.accept(self)
        for i in node.lines:
            i.accept(self)

    def visit_IndexNode(self, node):
        node.iobject.accept(self)
        node.lbracket.accept(self)
        node.index.accept(self)
        node.rbracket.accept(self)

    def visit_MethodNode(self, node):
        node.source_object.accept(self)
        node.dot.accept(self)
        node.name.accept(self)
        node.lpar.accept(self)
        node.args.accept(self)
        node.rpar.accept(self)

    def visit_FunctionNode(self, node):
        node.func_name.accept(self)
        node.lpar.accept(self)
        node.args.accept(self)
        node.rpar.accept(self)

    def visit_AssignmentNode(self, node):
        node.var_name.accept(self)
        node.operator.accept(self)
        node.value.accept(self)

    def visit_PlusAssignmentNode(self, node):
        self.visit_AssignmentNode(node)

    def visit_ForeachClauseNode(self, node):
        node.foreach_.accept(self)
        for varname, comma in zip_longest(node.varnames, node.commas):
            varname.accept(self)
            if comma is not None:
                comma.accept(self)
        node.colon.accept(self)
        node.items.accept(self)
        node.block.accept(self)
        node.endforeach.accept(self)

    def visit_IfClauseNode(self, node):
        for i in node.ifs:
            i.accept(self)
        node.elseblock.accept(self)
        node.endif.accept(self)

    def visit_UMinusNode(self, node):
        self.visit_UnaryOperatorNode(node)

    def visit_IfNode(self, node):
        node.if_.accept(self)
        node.condition.accept(self)
        node.block.accept(self)

    def visit_ElseNode(self, node):
        node.else_.accept(self)
        node.block.accept(self)

    def visit_TernaryNode(self, node):
        node.condition.accept(self)
        node.questionmark.accept(self)
        node.trueblock.accept(self)
        node.colon.accept(self)
        node.falseblock.accept(self)

    def visit_ArgumentNode(self, node):
        commas_iter = iter(node.commas)

        for arg in node.arguments:
            arg.accept(self)
            try:
                comma = next(commas_iter)
                comma.accept(self)
            except StopIteration:
                pass

        assert len(node.colons) == len(node.kwargs)
        for (key, val), colon in zip(node.kwargs.items(), node.colons):
            key.accept(self)
            colon.accept(self)
            val.accept(self)
            try:
                comma = next(commas_iter)
                comma.accept(self)
            except StopIteration:
                pass

    def visit_ParenthesizedNode(self, node):
        node.lpar.accept(self)
        node.inner.accept(self)
        node.rpar.accept(self)


class RawPrinter(FullAstVisitor):

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.result = ''

    def visit_node(self, node):
        self.result += node.value

    def visit_EmptyNode(self, node):
        pass

    def visit_BooleanNode(self, node):
        self.result += 'true' if node.value else 'false'

    def visit_NumberNode(self, node):
        self.result += node.raw_value

    def visit_StringNode(self, node):
        if node.is_fstring:
            self.result += 'f'
        if node.is_multiline:
            self.result += f"'''{node.value}'''"
        else:
            self.result += f"'{node.raw_value}'"

    def visit_ContinueNode(self, node):
        self.result += 'continue'

    def visit_BreakNode(self, node):
        self.result += 'break'


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("src_root")
    arg("--vs-orig", action = "store_true")
    arg("-a", "--ast-prefix", default = None, type = str)
    arg("-d", "--diff-with-parsed", action = "store_true")

    args = ap.parse_args()

    src_root = args.src_root
    vs_orig = args.vs_orig
    ast_prefix = args.ast_prefix
    diff_with_parsed = args.diff_with_parsed

    if vs_orig:
        from mesonbuild.mparser import (
            Parser as OrigParser,
        )
        t_rels = []
        diff_failings = []

    path_strip = len(src_root) + 1

    for dirpath, __, filenames in walk(src_root):
        for filename in filenames:
            if filename != "meson.build":
                continue

            fullfilename = join(dirpath, filename)
            print("Parsing %r" % (fullfilename,))
            with open(fullfilename, "r") as f:
                code = f.read()

            t0 = time()
            parser = Parser(code, fullfilename)
            try:
                ast = parser.parse()
            except:
                print_exc()
                failed = True
            else:
                failed = False
            t = time() - t0

            print("Parse time %0.3f" % (t,))

            if ast_prefix:
                ast_dir = ast_prefix + dirpath[path_strip:]
                if not isdir(ast_dir):
                    makedirs(ast_dir)
                ast_file = join(ast_dir, "prt." + filename)
                print("Printing ast to %r" % ast_file)
                printer = RawPrinter()
                ast.accept(printer)
                with open(ast_file, "w") as f:
                    f.write(printer.result)

                if diff_with_parsed:
                    orig_file_copy = join(ast_dir, "orig." + filename)
                    with open(orig_file_copy, "w") as f:
                        f.write(code)

            if vs_orig:

                t0 = time()
                parser = OrigParser(code, fullfilename)
                try:
                    # keep ref to ast to be as close to our implementation
                    # (dropping the ref may result in garbage collection)
                    orig_ast = parser.parse()
                except:
                    orig_failed = True
                else:
                    orig_failed = False
                t_orig = time() - t0

                print("Original parser time %.3f" % (t_orig,))
                t_diff = t - t_orig
                t_rel = t / t_orig
                print("Parse time diff %.8f, %.3f" % (t_diff, t_rel))
                t_rels.append(t_rel)

                if orig_failed != failed:
                    print("Failing mismatch")
                    diff_failings.append(fullfilename)

    if vs_orig:
        print("-- Original parser versus own...")
        n = len(t_rels)
        if n:
            t_rels_avg = sum(t_rels) / n
            print("Avg. parse time diff: %.3f" % (t_rels_avg,))

        print("Failing mismatches: %d" % (len(diff_failings),))


if __name__ == "__main__":
    exit(main() or 0)
