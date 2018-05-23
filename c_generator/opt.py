__all__ = [
    "optimize_function"
]

from common import (
    ObjectVisitor
)
from .generator import (
    OpAssign,
    BinaryOperator,
    OpCombAssign,
    OpDeclare,
    VariableUsage
)

class OptVisitor(ObjectVisitor):
    "OPTimizer visitor"

    def __init__(self, root):
        super(OptVisitor, self).__init__(root, field_name = "__descend__")

    def on_visit(self):
        cur = self.cur

        # replace expressions `a = a op b` with `a op= b`
        if isinstance(cur, OpAssign):
            op = cur.children[1]
            if not isinstance(op, BinaryOperator):
                return

            dst = cur.children[0]
            src0 = op.children[0]

            if isinstance(dst, OpDeclare):
                # TODO: OpAssign must become child of OpDeclare
                return

            if not (
                isinstance(dst, VariableUsage)
            and isinstance(src0, VariableUsage)
            ):
                return

            if dst.var is not src0.var:
                return

            src1 = op.children[1]

            new = OpCombAssign(dst, src1, op)

            new.set_parent(self)
            self.replace(new, skip_trunk = False)

def optimize_function(root):
    OptVisitor(root).visit()
