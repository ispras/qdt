#!/usr/bin/python

from collections import (
    defaultdict
)
from debug import (
    Watcher,
    TYPE_CODE_PTR
)
from common import (
    sort_topologically,
    lazy
)
from re import (
    compile
)
from graphviz import (
    Digraph
)


class RQOMTree(object):
    "QEmu object model tree descriptor at runtime"

    def __init__(self):
        self.name2type = {}
        self.addr2type = {}

        # Types are found randomly (i.e. not in parent-first order).
        self.unknown_parents = defaultdict(list)

    def account(self, impl, name = None, parent = None):
        """ Add a type.
    :type impl: debug.Value
    :param impl:
        is the value of type's `TypeImpl` struct
        """

        if impl.type.code == TYPE_CODE_PTR:
            # Pointer `impl` is definitely a value on the stack. It cannot be
            # used as a global. Same time `TypeImpl` is on the heap. Hence, it
            # can. I.e. a dereferenced `Value` should be used.
            impl = impl.dereference()
        if not impl.is_global:
            impl = impl.to_global()

        info_addr = impl.address

        t = RQOMType(self, impl, name = name, parent = parent)

        name = t.name
        parent = t.parent

        self.addr2type[info_addr] = t
        self.name2type[name] = t

        unk_p = self.unknown_parents

        n2t = self.name2type
        if parent in n2t:
            n2t[parent].children.append(t)
        else:
            unk_p[parent].append(t)

        if name in unk_p:
            t.children.extend(unk_p.pop(name))

        return t

    def __getitem__(self, addr_or_name):
        if isinstance(addr_or_name, str):
            return self.name2type[addr_or_name]
        else:
            return self.addr2type[addr_or_name]


class RQOMType(object):
    "QEmu object model type descriptor at runtime"

    def __init__(self, tree, impl, name = None, parent = None):
        """
    :type impl: debug.Value
    :param impl:
        is a global variable of type `TypeImpl`

    :type name: str
    :param name:
        is given if it is already known else it will be got from `impl`

    :type parent: str
    :param parent:
        is given if it is already known else it will be got from `impl`

        """
        self.tree = tree
        self.impl = impl
        if name is None:
            name = impl["name"].fetch_c_string()
        if parent is None:
            parent = impl["parent"].fetch_c_string()
            # Parent may be None
        self.name, self.parent = name, parent

        self.children = []

        # Instance pointer can be casted to different C types. Remember those
        # types.
        self._instance_casts = set()

        # "device"
        self.realize = None

    def instance_casts(self):
        """ A QOM instance can also be casted to C types those corresponds to
ancestors.
    :returns: list of possible casts (debug.Type)
        """
        ret = set(self._instance_casts)
        for a in self.iter_ancestors():
            for cast in a._instance_casts:
                ret.add(cast)
        return ret

    # TODO: there is too many boilerplate code for `TypeImpl` fields access.
    # Consider to rewrite it in a common way. `__getitem__` ?

    @lazy
    def instance_init(self):
        impl = self.impl

        addr = impl["instance_init"].fetch_pointer()
        if addr:
            return impl.dic.subprogram(addr)
        return None

    @lazy
    def class_init(self):
        impl = self.impl

        addr = impl["class_init"].fetch_pointer()
        if addr:
            return impl.dic.subprogram(addr)
        return None

    def __dfs_children__(self):
        return self.children

    def iter_ancestors(self):
        n2t = self.tree.name2type
        cur = self.parent

        while cur is not None:
            t = n2t[cur]
            yield t
            cur = t.parent

    def implements(self, name):
        if name == self.name:
            return True

        try:
            t = self.tree.name2type[name]
        except KeyError:
            # the type given is unknown, `self` cannot implement it
            return False

        for a in self.iter_ancestors():
            if a is t:
                return True
        return False


# Characters disallowed in node ID according to DOT language. That is not a
# full list though.
# https://www.graphviz.org/doc/info/lang.html
re_DOT_ID_disalowed = compile(r"[^a-zA-Z0-9_]")


def gv_node(label):
    return re_DOT_ID_disalowed.sub("_", label)


class QOMTreeReverser(Watcher):
    """ Sets breakpoints on key places of QOM tree initialization and reverses
the QOM tree by fetching relevant data.
    """

    def __init__(self, dic, interrupt = True, verbose = False):
        """
    :param interrupt:
        Stop QEmu and exit `RemoteTarget.run` after QOM module is initialized.
        """
        super(QOMTreeReverser, self).__init__(dic, verbose = verbose)

        self.tree = RQOMTree()
        self.interrupt = interrupt

    def on_type_register_internal(self):
        # type_register_internal

        # v2.12.0
        "object.c:139"

        t = self.tree.account(self.rt["ti"])

        if self.verbose:
            print("%s -> %s" % (t.parent, t.name))

    def on_type_initialize(self):
        # now the type and its ancestors are initialized

        # v2.12.0
        "object.c:344"

        rt = self.rt
        type_impl = rt["ti"]

        ti_addr = type_impl.fetch_pointer()
        a2t = self.tree.addr2type

        if ti_addr not in a2t:
            # There are interfaces providing variations of regular types. They
            # do not path through type_register_internal because its `TypeInfo`
            # is created and used directly by type_initialize_interface.
            return

        t = a2t[ti_addr]

        if t.implements("device"):
            cls = type_impl["class"]

            dev_cls = cls.cast("DeviceClass *")
            realize_addr = dev_cls["realize"].fetch_pointer()

            if realize_addr:
                t.realize = rt.dic.subprogram(realize_addr)

    def on_main(self):
        # main, just after QOM module initialization

        # v2.12.0
        "vl.c:3075"

        if self.interrupt:
            self.rt.target.interrupt()

    def to_file(self, dot_file_name):
        "Writes QOM tree to Graphviz file."

        graph = Digraph(
            name = "QOM",
            graph_attr = dict(
                rankdir = "LR"
            ),
            node_attr = dict(
                shape = "polygon",
                fontname = "Momospace"
            ),
            edge_attr = dict(
                style = "filled"
            ),
        )

        for t in sort_topologically(
            v for v in self.tree.name2type.values() if v.parent is None
        ):
            n = gv_node(t.name)
            label = t.name + "\\n0x%x" % t.impl.address
            if t._instance_casts:
                label += "\\n*"
                for cast in t._instance_casts:
                    label += "\\n" + cast.name

            graph.node(n, label = label)
            if t.parent:
                graph.edge(gv_node(t.parent), n)

        with open(dot_file_name, "wb") as f:
            f.write(graph.source)


def main():
    return 0

if __name__ == "__main__":
    exit(main())
