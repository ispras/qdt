__all__ = [
    "expression2gv"
]

from graphviz import (
    Digraph
)
from .expression import (
    Expression,
    Constant,
    AddressSize,
    FrameBase,
    ObjectAddress
)
from six import (
    integer_types
)

strable = (Constant, AddressSize, FrameBase, ObjectAddress) + integer_types


class ExprDigraph(Digraph):

    def node(self, expr):
        cls = type(expr).__name__
        name = "%s_%x" % (cls, id(expr))

        if isinstance(expr, strable):
            super(ExprDigraph, self).node(name, label = str(expr))
        else:
            super(ExprDigraph, self).node(name, label = cls)
        return name


def expression2gv(expr):
    "Given `Expression` instance returns it as a graph in graphviz format."

    graph = ExprDigraph(
        name = "Expr 0x%x" % id(expr),
        graph_attr = dict(rankdir = "TB"),
        node_attr = dict(shape = "polygon", fontname = "Courier New"),
        edge_attr = dict(style = "filled")
    )

    name = graph.node(expr)
    queue = [(expr, name)]

    while queue:
        parent, pname = queue.pop(0)

        for r in parent.refs:
            name = graph.node(r)
            graph.edge(pname, name)

            if isinstance(r, Expression):
                queue.append((r, name))

    return graph.source
