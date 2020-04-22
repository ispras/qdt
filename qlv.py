#!/usr/bin/python

# QEMU log viewer
from argparse import (
    ArgumentParser
)
from widgets import (
    Statusbar,
    add_scrollbars_native,
    AutoPanedWindow,
    GUIText,
    READONLY,
    BOTH,
    GUIFrame,
    GUITk,
    VarTreeview
)
from six.moves.tkinter import (
    IntVar,
    RAISED,
    VERTICAL,
    HORIZONTAL,
    NONE,
    END,
    Scrollbar
)
from six.moves.tkinter_ttk import (
    Style
)
from common import (
    ee,
    mlget as _
)
from six.moves import (
    zip as izip,
    range as xrange,
)
from qemu import (
    QEMULog
)
from time import (
    time,
)


# less value = more info
DEBUG = ee("QLOG_DEBUG", "3")


# Instructions Treeview styles
STYLE_DEFAULT = tuple()
STYLE_DIFFERENCE = ("difference",)
STYLE_FIRST = ("first",)

class InstructionsTreeview(VarTreeview):

    def __init__(self, master, **kw):
        kw["columns"] = [
            "addr",
            "size",
            "disas"
        ]

        VarTreeview.__init__(self, master, **kw)

        self.heading("addr", text = _("Address"))
        self.heading("size", text = _("Size"))
        self.heading("disas", text = _("Disassembly"))
        self.column("#0", width = 10)
        self.column("addr", minwidth = 120, width = 120)
        self.column("size", minwidth = 30, width = 30)
        self.column("disas", width = 600)

        self.tag_configure(STYLE_FIRST[0], background = "#EEEEEE")
        self.tag_configure(STYLE_DIFFERENCE[0], background = "#FF0000")


# Trace text (CPU state) styles.
STYLE_FILE = ("file",)
STYLE_WARNING = ("warning",)
# STYLE_DIFFERENCE of InstructionsTreeview is also used

class QLVWindow(GUITk):

    def __init__(self):
        GUITk.__init__(self)

        self.title(_("QEmu Log Viewer"))

        self.columnconfigure(0, weight = 1)

        self.rowconfigure(0, weight = 1)
        panes = AutoPanedWindow(self, orient = VERTICAL, sashrelief = RAISED)
        panes.grid(row = 0, column = 0, sticky = "NESW")

        fr_instructions = GUIFrame(panes)
        panes.add(fr_instructions)

        fr_instructions.rowconfigure(0, weight = 1)
        fr_instructions.columnconfigure(0, weight = 1)
        fr_instructions.columnconfigure(1, weight = 0)

        tv = InstructionsTreeview(fr_instructions)
        self.tv_instructions = tv
        tv.grid(row = 0, column = 0, sticky = "NESW")
        tv.bind("<<TreeviewSelect>>", self._on_instruction_selected, "+")

        vscroll = Scrollbar(fr_instructions)
        vscroll.grid(row = 0, column = 1, sticky = "NS")

        tv.config(yscrollcommand = vscroll.set)
        vscroll.config(command = tv.yview)

        # Showing trace message (CPU registers, etc.).
        self.panes_trace_text = panes_trace_text = AutoPanedWindow(panes,
            orient = HORIZONTAL,
            sashrelief = RAISED
        )
        panes.add(panes_trace_text)

        self.rowconfigure(1, weight = 0)
        self.sb = sb = Statusbar(self)
        sb.grid(row = 1, column = 0, sticky = "EWS")
        self.var_inst_n = var = IntVar(self)

        sb.right(_("Instructions"))
        sb.right(var)

        self.qlog_trace_texts = []

    def show_logs(self, qlogs):
        panes_trace_text = self.panes_trace_text
        qlog_trace_texts = self.qlog_trace_texts
        # TODO: re-usage?

        for __ in qlogs:
            fr_trace_text = GUIFrame(panes_trace_text)
            panes_trace_text.add(fr_trace_text)

            fr_trace_text.rowconfigure(0, weight = 1)
            fr_trace_text.columnconfigure(0, weight = 1)

            trace_text = GUIText(fr_trace_text, state = READONLY, wrap = NONE)
            qlog_trace_texts.append(trace_text)

            trace_text.grid(row = 0, column = 0, sticky = "NESW")

            add_scrollbars_native(fr_trace_text, trace_text)

            trace_text.tag_configure(STYLE_FILE[0], foreground = "#AAAAAA")
            trace_text.tag_configure(STYLE_WARNING[0], foreground = "#FFBB66")
            trace_text.tag_configure(STYLE_DIFFERENCE[0],
                foreground = "#FF0000"
            )

        self.task_manager.enqueue(self.co_trace_builder(qlogs))

    def co_trace_builder(self, qlogs):
        t1 = time()

        tv = self.tv_instructions
        var_inst_n = self.var_inst_n

        self.qlogs = qlogs

        # Instructions are kept in lists: one per qlog.
        # This is list of those lists.
        self.all_instructions = all_instructions = list(list() for _ in qlogs)

        trace_iters = list(qlog.iter_instructions() for qlog in qlogs)
        idx = 0

        while True:
            start_idx = idx
            end_idx = idx + 100

            # Build subtrace for first log and then try to compare it with
            # subtraces of rest logs.

            iter_of_iters = iter(trace_iters)

            subtrace = list(
                izip(xrange(start_idx, end_idx), next(iter_of_iters))
            )

            if not subtrace:
                print("Trace has been built")
                break

            all_instructions[0].extend(t[1] for t in subtrace)
            var_inst_n.set(start_idx + len(subtrace))

            difference = None

            for log_idx, qlog_iter_2 in enumerate(iter_of_iters, 1):
                i1_idx = start_idx - 1

                log_instrs = all_instructions[log_idx]

                for (i1_idx, i1), i2 in izip(subtrace, qlog_iter_2):
                    log_instrs.append(i2)

                    # Currently, comparison is address based only.
                    if i1.addr != i2.addr:
                        # Indexes are same until first difference.
                        difference = (i1_idx, i2)
                        break

                compared = i1_idx - start_idx + 1
                if compared < len(subtrace):
                    # Log 2 ended earlier.
                    subtrace = subtrace[:compared]

                if difference is not None:
                    break

            if not subtrace:
                print("Trace has been built")
                break

            for idx, i in subtrace:
                if DEBUG < 3:
                    print("0x%08X: %s" % (i.addr, i.disas))
                tv.insert("", "end",
                    text = str(idx),
                    tags = STYLE_FIRST if i.first else STYLE_DEFAULT,
                    values = ("0x%08X" % i.addr, "-", str(i.disas))
                )

            if difference:
                idx, i = difference
                iid = tv.insert("", "end",
                    text = str(idx),
                    tags = STYLE_DIFFERENCE,
                    values = ("0x%08X" % i.addr, "-", str(i.disas))
                )
                tv.see(iid)
                print("Difference found, stopping")
                break

            idx += 1
            # No more instructions in the trace
            if idx < end_idx:
                print("Trace has been built")
                break

            yield True

        t2 = time()
        print("In %f second(s)" % (t2 - t1))

    def _on_instruction_selected(self, __):
        tv = self.tv_instructions
        qlog_trace_texts = self.qlog_trace_texts
        qlogs = self.qlogs

        for trace_text in qlog_trace_texts:
            trace_text.delete("1.0", END)

        sel = tv.selection()
        if not sel:
            return

        row_text = tv.item(sel[0], "text")

        try:
            idx = int(row_text)
        except ValueError:
            return

        left_trace = None

        for qlog_idx, (qlog_instrs, trace_text) in enumerate(izip(
            self.all_instructions, qlog_trace_texts
        )):
            try:
                i = qlog_instrs[idx]
            except IndexError:
                continue

            trace_text.insert(END, qlogs[qlog_idx].file_name + "\n",
                STYLE_FILE
            )

            trace = i.trace

            if trace is None:
                trace_text.insert(END, _("No CPU data").get() + "\n",
                    STYLE_WARNING
                )
            else:
                if qlog_idx == 0:
                    left_trace = trace.as_text
                    trace_text.insert(END, left_trace)
                else:
                    cur_trace = trace.as_text
                    if left_trace is None:
                        # Left log has no trace record for this instruction.
                        # Nothing to diff.
                        trace_text.insert(END, cur_trace)
                    else:
                        insert_diff(trace_text, left_trace, cur_trace)

def insert_diff(text_wgt, base, new):
    a, b = base.split("\n"), new.split("\n")

    biter = iter(b)

    for la, lb in izip(a, biter):
        cbiter = iter(lb)
        for ca, cb in izip(la, cbiter):
            if ca == cb:
                text_wgt.insert(END, cb)
            else:
                text_wgt.insert(END, cb, STYLE_DIFFERENCE)

        for cb in cbiter:
            text_wgt.insert(END, cb)

        text_wgt.insert(END, "\n")

    for lb in biter:
        text_wgt.insert(END, lb + "\n")


def main():
    ap = ArgumentParser(
        prog = "QEMU Log Viewer"
    )
    DEFAULT_LIMIT = "1000"
    ap.add_argument("-l",
        metavar = "N",
        default = DEFAULT_LIMIT,
        help = "limit number of log lines (default %s)" % DEFAULT_LIMIT
    )
    # Note, code below assumes that there is at least one log.
    ap.add_argument("qlog", nargs = "+")

    args = ap.parse_args()

    qlogs = []
    for qlogFN in args.qlog:
        print("Start feeding of " + qlogFN)

        qlog = QEMULog(qlogFN, int(args.l))

        qlogs.append(qlog)

    if len(qlogs) > 1:
        print("Comparison mode")

    tk = QLVWindow()
    tk.geometry("1200x800")

    tkstyle = Style()
    tkstyle.configure("Treeview", font = ("Courier", 10))

    print("Building full trace(s)")
    # Launch trace building (and comparison).
    tk.show_logs(qlogs)

    tk.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
