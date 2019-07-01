__all__ = [
    "QType"
  , "co_gen_device_tree"
  , "from_legacy_dict"
]

from .qemu_watcher import (
    QOMTreeReverser
)
from debug import (
    create_dwarf_cache,
    Runtime,
    GitLineVersionAdapter
)
from copy import (
    deepcopy as dcp
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

        self.macros = macros if macros else []

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

    # Tree will be traversed from the root to the child nodes
    # The children will be serialized first
    __pygen_deps__ = ("children",)

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self, skip_list = ["parent"])
        gen.gen_end()

def from_dict(d, parent = None):
    res = QType(d["type"], parent = parent)
    for key, val in d.items():
        if key == "children":
            continue
        if key == "type":
            continue
        setattr(res, key, dcp(val))
    return res

def from_legacy_dict(dt):
    stack = [(None, dt[0])]
    while stack:
        parent, tdict = stack.pop()
        t = from_dict(tdict, parent = parent)

        try:
            children = tdict["children"]
        except KeyError:
            continue

        stack.extend((t, child_dict) for child_dict in children)

    # note that any intermediate value is proper
    return t.root()


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


def co_gen_device_tree(bindir, src_path, target_list, root):
    for arch_name in target_list:
        qemu_exec = join(bindir, "qemu-system-" + arch_name)

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

        yield rt.co_run_target()

        yield co_fill_children(
            qomtr.tree.name2type["device"],
            root,
            arch_name
        )
