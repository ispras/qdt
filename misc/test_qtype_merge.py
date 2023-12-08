#!/usr/bin/env python3

from qemu import (
    QType,
)

from timeit import (
    timeit,
)


class QType(QType):

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
