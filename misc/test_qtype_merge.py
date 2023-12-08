from timeit import (
    timeit,
)


class QType(object):
    """ Node in QOM type tree """
    def __init__(self, name,
            parent = None,
            children = None,
            macros = None,
            arches = None
        ):
        self.name = name

        # name: reference
        self.children = children if children else {}
        for c in self.children.values():
            c.parent = self

        if parent is None:
            self.parent = None
        else:
            parent.add_child(self)

        self.macros = list(macros) if macros else []

        # set of CPU architectures found in QOM type tree
        self.arches = set(arches) if arches else set()

    def add_child(self, child):
        self.children[child.name] = child
        child.parent = self

    def merge(self, tree):
        # cache
        children = self.children
        macros = self.macros
        add_child = self.add_child

        for m in tree.macros:
            if m not in macros:
                macros.append(m)

        self.arches.update(tree.arches)

        for n, other_c in tree.children.items():

            if n in children:
                c = children[n]
            else:
                c = type(other_c)(
                    name = n,
                    macros = other_c.macros,
                    arches = other_c.arches,
                )
                add_child(c)

            c.merge(other_c)

    def merge2(self, tree):
        # cache
        children = self.children
        macros = self.macros

        for m in tree.macros:
            if m not in macros:
                macros.append(m)

        self.arches.update(tree.arches)

        for n, other_c in tree.children.items():

            if n in children:
                c = children[n]
            else:
                c = type(other_c)(
                    name = n,
                    parent = self,
                    macros = other_c.macros,
                    arches = other_c.arches,
                )

            c.merge2(other_c)


if __name__ == "__main__":
    setup = '''\
r2 = tmp = QType("root2")
for i in range(500):
    tmp = QType("d" + str(i), parent = tmp)
'''

    # Comparison of explicitly adding a child using QType.add_child and
    # implicitly adding a child using QType.parent attribute.
    print(timeit('QType("root1").merge(r2)',
        setup = setup,
        number = 1000,
        globals = globals(),
    ))
    print(timeit('QType("root1").merge2(r2)',
        setup = setup,
        number = 1000,
        globals = globals(),
    ))
