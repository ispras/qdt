__all__ = [
    "QType"
  , "co_update_device_tree"
  , "co_fill_children"
]

from .qemu_watcher import (
    QOMTreeReverser
)
from debug import (
    InMemoryELFFile,
    Runtime,
    GitLineVersionAdapter
)
from common import (
    pypath,
    co_find_eq
)
from subprocess import (
    Popen
)
# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.rsp import (
        AMD64
    )
    from pyrsp.utils import (
        find_free_port,
        wait_for_tcp_port
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

    def __remove_child(self, child):
        child.parent = None
        del self.children[child.name]

    def add_child(self, child):
        self.children[child.name] = child
        child.parent = self

    def unparent(self):
        self.parent.__remove_child(self)

    def root(self):
        """ returns root node, a one with `None` parent """
        root = self
        parent = root.parent
        while parent is not None:
            root = parent
            parent = root.parent
        return root

    def descendants(self):
        """ enumerates all nodes in depth-first order starting from self """
        root = self.root()
        stack = [root]

        while stack:
            e = stack.pop()
            yield e
            c = e.children
            if c:
                stack.extend(c.values())

    def find(self, **request):
        """ searches for the request across entire tree starting from root """
        for t in co_find_eq(self.root().descendants(), **request):
            yield t

    def merge(self, tree):
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

            c.merge(other_c)

    def __contains__(self, name):
        return name in self.children

    def rename(self, name):
        parent = self.parent # cache

        if parent:
            if name in parent:
                raise ValueError("The parent `%s` already has a type `%s`" % (
                    parent.name, name
                ))
            self.unparent()
            self.name = name
            parent.add_child(self)
        else:
            self.name = name

    # Tree will be traversed from the root to the child nodes
    # The children will be serialized first
    __pygen_deps__ = ("children",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self, skip_kw = ["parent"])
        gen.gen_end()


def co_fill_children(qomtr_node, qtype_node, arch):
    for c in qomtr_node.children:
        name = c.name
        if name in qtype_node.children:
            # Node already exists.
            # We only need to add the new CPU arch
            qt = qtype_node.children[name]
        else:
            qt = QType(name)
            qtype_node.add_child(qt)

        qt.arches.add(arch)

        yield co_fill_children(c, qt, arch)


def co_update_device_tree(qemu_exec, src_path, arch_name, root):
    elf = InMemoryELFFile(qemu_exec)
    dic = elf.create_dwarf_cache()

    gvl_adptr = GitLineVersionAdapter(src_path)

    qomtr = QOMTreeReverser(dic,
        interrupt = True,
        verbose = True,
        line_adapter = gvl_adptr
    )

    # Update GLV adapter cache now to use it during next device tree updating.
    yield True

    gvl_adptr.cm.store_cache()

    port = find_free_port(4321)
    qemu_debug_addr = "localhost:%u" % port
    Popen(["gdbserver", qemu_debug_addr, qemu_exec])

    if not wait_for_tcp_port(port):
        raise RuntimeError("gdbserver does not listen %u" % port)

    yield True

    # XXX: simplified PIE and non-PIE executables distinction
    # more detailed information: https://stackoverflow.com/a/55704865
    if elf["e_type"] != "ET_EXEC":
        # GDB turns off address randomization by default and loads program at
        # the default address ELF_ET_DYN_BASE.
        # TODO: determine address dynamically
        base_address = 0x0000555555554000
    else:
        base_address = 0

    yield True

    qemu_debugger = AMD64(str(port), noack = True)
    rt = Runtime(qemu_debugger, dic, base_address = base_address)

    qomtr.init_runtime(rt)

    yield rt.co_run_target()

    device_subtree = qomtr.tree.name2type.get("device", None)

    if device_subtree is None:
        raise RuntimeError('No "device" QOM subtree. Did you forget to pass ' +
            '"--extra-cflags=-no-pie" and/or "--disable-pie" to `configure`?'
        )

    yield co_fill_children(
        device_subtree,
        root,
        arch_name
    )
