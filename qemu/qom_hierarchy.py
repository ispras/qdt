__all__ = [
    "QType"
  , "co_gen_device_tree"
]

from .machine_watcher import (
    QOMTreeReverser,
    co_run_target
)
from debug import (
    create_dwarf_cache,
    Runtime,
    GitLineVersionAdapter
)
from common import (
    pypath,
    co_find_eq
)
from os.path import (
    join
)
from multiprocessing import (
    Process
)
from os import (
    system
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
    def __init__(self, name, children = None, macro = None, arches = None):
        self.name = name

        # name: reference
        self.children = children if children else {}
        for c in self.children.values():
            c.parent = self

        # list of macros corresponding to QType.name
        self.macro = macro if macro else []

        self.parent = None

        # set of CPU architectures found in QOM type tree
        self.arches = arches if arches else set()

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

    # Python serialization
    # Tree will be traversed from the root to the child nodes
    # And the children will be serialized first
    __pygen_deps__ = ("children",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self)
        gen.gen_end()


def co_gen_device_tree(build_path, src_path, target_list, root):
    bin_folder = join(build_path, "bin")
    for arch_name in target_list:
        qemu_exec = join(bin_folder, "qemu-system-" + arch_name)

        dic = create_dwarf_cache(qemu_exec)

        gvl_adptr = GitLineVersionAdapter(src_path)

        qomtr = QOMTreeReverser(dic,
            interrupt = True,
            verbose = True,
            line_adapter = gvl_adptr
        )

        port = find_free_port(4321)
        qemu_debug_addr = "localhost:%u" % port
        qemu_proc = Process(
            target = system,
            args = (" ".join(["gdbserver", qemu_debug_addr, qemu_exec]),)
        )
        qemu_proc.start()

        if not wait_for_tcp_port(port):
            raise RuntimeError("gdbserver does not listen %u" % port)

        yield True

        qemu_debugger = AMD64(str(port), noack = True)
        rt = Runtime(qemu_debugger, dic)

        qomtr.init_runtime(rt)

        yield co_run_target(rt)

        def co_fill_children(qomtr_node, qtype_node):
            for c in qomtr_node.children:
                name = c.name
                if name in qtype_node.children:
                    # Node already exists.
                    # We only need to add the new CPU arch
                    qt = qtype_node.children[name]
                    qt.arches.add(arch_name)
                else:
                    qt = QType(name, arches = set([arch_name]))
                    qtype_node.add_child(qt)

                yield co_fill_children(c, qt)

        yield co_fill_children(
            qomtr.tree.name2type["device"],
            root
        )
