__all__ = [
    "VarDeclarator"
]

from ..model import (
    NodeVisitor,
    Variable,
)
from .tree import (
    Declare,
)
from collections import (
    defaultdict,
)


class VarDeclarator(NodeVisitor):

    def __init__(self, root, arguments):
        super(VarDeclarator, self).__init__(root)

        self.arguments = set(arguments or [])
        self.declared = set()
        self.variables = set()

    def on_visit(self):
        cur = self.cur

        if isinstance(cur, Variable):
            self.variables.add(cur)
        elif isinstance(cur, Declare):
            self.declared.update(cur.iter_variables())
        # Note, `OpDeclareAssign` is only correct within `Declare` and is
        # considered by `iter_variables`.

    def visit(self):
        ret = super(VarDeclarator, self).visit()

        # cache
        variables = self.variables

        name2vars = defaultdict(list)

        # Detect same named variables among all.
        for v in variables:
            name2vars[v.name].append(v)

        # Do not declare globals.
        global_vars = set(
            v for v in variables if (
                v.declarer is not None or v.definer is not None
            )
        )

        undeclared = variables - self.declared - self.arguments - global_vars
        undeclared_names = set(v.name for v in undeclared)

        # After visitting `cur` `is` `root`.
        root_children = self.cur.children

        # Be deterministic.
        name_and_vars = sorted(name2vars.items())

        # Inserting at 0 does reverse the order.
        for name, vars_ in reversed(name_and_vars):
            if name not in undeclared_names:
                continue

            if len(vars_) > 1:
                # TODO: support this
                #     1. types are same: replace one with another
                #     2. declare each in its scope
                #     3. same scope: report redefinition error
                print("Auto declaration of same named variables is not"
                    " supported (%s)." % name
                )
                # Neither variable will be declared because `set` iteration
                # order is random under Py3 (`self.variables`).
                continue

            v = vars_[0]

            root_children.insert(0, Declare(v))

        return ret
