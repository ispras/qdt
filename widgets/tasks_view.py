__all__ = [
    "TasksFrame"
  , "gen_task_graph"
  , "TaskNode"
  , "TaskState"
  , "TasksWindow"
]

from common import (
    bidict,
    mlget as _,
)
from .gui_frame import (
    GUIFrame,
)
from .gui_toplevel import (
    GUIToplevel,
)
from .scrollframe import (
    add_scrollbars_native,
)

from collections import (
    defaultdict,
    deque,
)
from six.moves.tkinter import (
    BOTH,
    END,
)
from six.moves.tkinter_ttk import (
    Treeview,
)


class TaskState:
    class TS_ACTIVE: pass
    class TS_CALLER: pass
    class TS_IO_READ: pass
    class TS_IO_WRITE: pass
    class TS_WAITING: pass

class TaskNode(object):

    def __init__(self):
        self.state = TaskState.TS_ACTIVE

    def __lt__(self, n):
        return self.name < n.name


def gen_task_graph(co_disp):
    nodes = defaultdict(TaskNode)
    roots = set(nodes[t] for t in co_disp.active_tasks)

    for caller, callee in co_disp.callers.items():
        n_caller = nodes[caller]
        roots.discard(nodes[callee])
        roots.add(n_caller)
        n_caller.state = TaskState.TS_CALLER
        n_caller.callee = callee

    for io, t in co_disp.io2read.items():
        n_t = nodes[t]
        n_t.state = TaskState.TS_IO_READ
        n_t.io = io

    for io, t in co_disp.io2write.items():
        n_t = nodes[t]
        n_t.state = TaskState.TS_IO_WRITE
        n_t.io = io

    for t in co_disp.tasks:
        n_t = nodes[t]
        n_t.state = TaskState.TS_WAITING
        roots.add(n_t)

    for t, n in nodes.items():
        n.name = t.generator.__name__
        n.description = t.description.get()

    return nodes, roots


class TasksFrame(GUIFrame):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)

        GUIFrame.__init__(self, *a, **kw)

        self._tv = tv = Treeview(self,
            show = "tree",
            columns = ["desc"],
        )
        self._tv_cache = deque()
        self._tn2iid = tn2iid = bidict()
        self._iid2tn = tn2iid.mirror

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)
        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv, sizegrip = sizegrip)

        tv.tag_configure(TaskState.TS_ACTIVE,
            foreground = "#000000",
            background = "#FFFFFF",
        )
        tv.tag_configure(TaskState.TS_CALLER,
            foreground = "#000000",
            background = "#CCCCCC",
        )
        tv.tag_configure(TaskState.TS_IO_READ,
            foreground = "#00FF00",
            background = "#000000",
        )
        tv.tag_configure(TaskState.TS_IO_WRITE,
            foreground = "#FF0000",
            background = "#000000",
        )
        tv.tag_configure(TaskState.TS_WAITING,
            foreground = "#888888",
            background = "#FFFFFF",
        )

    def update_tree(self, co_disp):
        tv = self._tv
        cache = self._tv_cache
        iid2tn, tn2iid = self._iid2tn, self._tn2iid

        nodes, roots = gen_task_graph(co_disp)
        used = set()
        use = used.add

        roots = sorted(list(roots))

        stack = [("", r) for r in roots]
        while stack:
            parent_iid, node = stack.pop()

            try:
                node_iid = tn2iid[node]
            except KeyError:
                try:
                    node_iid = cache.pop()
                except IndexError:
                    node_iid = tv.insert(parent_iid, END)
                else:
                    tv.move(node_iid, parent_iid, END)
                tn2iid[node] = node_iid

            cfg = dict(
                text = node.name,
                values = [
                    node.description,
                ],
                open = True,
                tags = [node.state],
            )

            tv.item(node_iid, **cfg)
            use(node_iid)

            if node.state is TaskState.TS_CALLER:
                stack.append((node_iid, nodes[node.callee]))

        stack = list(tv.get_children(""))
        while stack:
            iid = stack.pop()
            stack.extend(tv.get_children(iid))
            if iid not in used:
                cache.append(iid)
                tv.detach(iid)
                del iid2tn[iid]

    _after__periodic_update = None
    def start_periodic_update(self, co_disp, period = 100):
        if self._after__periodic_update:
            self.after_cancel(self._after__periodic_update)
        def periodic_update():
            self.update_tree(co_disp)
            self._after__periodic_update = self.after(period, periodic_update)
        self._after__periodic_update = self.after(period, periodic_update)

    def stop_periodic_update(self):
        self.after_cancel(self._after__periodic_update)


class TasksWindow(GUIToplevel):

    def __init__(self, guitk, *a, **kw):
        GUIToplevel.__init__(self, master = guitk, *a, **kw)

        self.title(_("Tasks"))

        self._tf = tf = TasksFrame(self, sizegrip = True)
        tf.pack(fill = BOTH, expand = True)

        tf.start_periodic_update(self.master.task_manager)
