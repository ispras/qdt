__all__ = [
    "Operand"
      , "VariableOperand"
  , "Operator"
      , "BinaryOperator"
          , "AssignmentOperator"
  , "CodeNode"
]

class Operand():
    def __init__(self, name, data_references = []):
        self.name = name
        self.data_references = data_references

class VariableOperand(Operand):
    def __init__(self, var):
        super(VariableOperand, self).__init__(
            "reference to variable {}".format(var.name), [var])

class Operator():
    def __init__(self, fmt, operands):
        self.format = fmt
        self.operands = operands

class BinaryOperator(Operator):
    def __init__(self, name, operands):
        fmt = "{{}} {} {{}}".format(name);
        super(BinaryOperator, self).__init__(fmt, operands)

class AssignmentOperator(BinaryOperator):
    def __init__(self, operands):
        super(AssignmentOperator, self).__init__("=", operands)


class CodeNode():
    def __init__(self, name, code, used_types = None, node_references = None):
        self.name = name
        self.code = code
        self.node_users = []
        self.node_references = []
        self.used_types = set()
