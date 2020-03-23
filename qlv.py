#!/usr/bin/python

# QEMU log viewer
from argparse import (
    ArgumentParser
)
from itertools import (
    zip_longest,
)
from widgets import (
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
    TraceInstr,
    QEMULog
)


# less value = more info
DEBUG = ee("QLOG_DEBUG", "3")


STYLE_DIFFERENCE = ("difference",)

def insert_diff(text_wgt, base, new):
    a, b = base.split("\n"), new.split("\n")
    # The naive algorithm below assumes that CPU states always have lines of
    # same length. Differences are only possible in char values.

    for la, lb in izip(a, b):
        for ca, cb in zip_longest(la, lb):
            if cb is None:
                break

            if ca == cb:
                text_wgt.insert(END, cb)
            else:
                text_wgt.insert(END, cb, STYLE_DIFFERENCE)

        text_wgt.insert(END, "\n")


if __name__ == "__main__":
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

    print("Building full trace(s)")

    tk = GUITk()
    tk.title(_("QEmu Log Viewer"))
    tk.geometry("1200x800")

    panes = AutoPanedWindow(tk, orient = VERTICAL, sashrelief = RAISED)
    panes.pack(fill = BOTH, expand = True)

    fr_instructions = GUIFrame(panes)
    panes.add(fr_instructions)

    fr_instructions.rowconfigure(0, weight = 1)
    fr_instructions.columnconfigure(0, weight = 1)
    fr_instructions.columnconfigure(1, weight = 0)

    tkstyle = Style()
    tkstyle.configure("Treeview", font = ("Courier", 10))

    columns = [
        "addr",
        "size",
        "disas"
    ]

    tv = VarTreeview(fr_instructions, columns = columns)
    tv.heading("addr", text = _("Address"))
    tv.heading("size", text = _("Size"))
    tv.heading("disas", text = _("Disassembly"))
    tv.column("#0", width = 10)
    tv.column("addr", minwidth = 120, width = 120)
    tv.column("size", minwidth = 30, width = 30)
    tv.column("disas", width = 600)

    tv.tag_configure("first", background = "#EEEEEE")
    STYLE_FIRST = ("first",)

    tv.tag_configure(STYLE_DIFFERENCE[0], background = "#FF0000")

    STYLE_DEFAULT = tuple()

    tv.grid(row = 0, column = 0, sticky = "NESW")

    vscroll = Scrollbar(fr_instructions)
    vscroll.grid(row = 0, column = 1, sticky = "NS")

    tv.config(yscrollcommand = vscroll.set)
    vscroll.config(command = tv.yview)

    trace_iters = list(qlog.pipeline for qlog in qlogs)

    # Instructions are kept in lists: one per qlog.
    # This is list of those lists.
    all_instructions = list(list() for _ in qlogs)

    def co_trace_builder():
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


    # Showing trace message (CPU registers, etc.).

    panes_trace_text = AutoPanedWindow(panes,
        orient = HORIZONTAL,
        sashrelief = RAISED
    )
    panes.add(panes_trace_text)

    qlog_trace_texts = []

    for __ in qlogs:
        fr_trace_text = GUIFrame(panes_trace_text)
        panes_trace_text.add(fr_trace_text)

        fr_trace_text.rowconfigure(0, weight = 1)
        fr_trace_text.columnconfigure(0, weight = 1)

        trace_text = GUIText(fr_trace_text, state = READONLY, wrap = NONE)
        qlog_trace_texts.append(trace_text)

        trace_text.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(fr_trace_text, trace_text)

        trace_text.tag_configure("file", foreground = "#AAAAAA")
        trace_text.tag_configure("warning", foreground = "#FFBB66")
        trace_text.tag_configure(STYLE_DIFFERENCE[0], foreground = "#FF0000")

    STYLE_FILE = ("file",)
    STYLE_WARNING = ("warning",)

    def on_instruction_selected(__):
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
            all_instructions, qlog_trace_texts
        )):
            try:
                i = qlog_instrs[idx]
            except IndexError:
                continue

            trace_text.insert(END, args.qlog[qlog_idx] + "\n", STYLE_FILE)

            if isinstance(i, TraceInstr):
                if qlog_idx == 0:
                    left_trace = i.trace.as_text
                    trace_text.insert(END, left_trace)
                else:
                    cur_trace = i.trace.as_text
                    if left_trace is None:
                        # Nothing to diff
                        trace_text.insert(END, cur_trace)
                    else:
                        insert_diff(trace_text, left_trace, cur_trace)
            else:
                trace_text.insert(END, _("No CPU data").get() + "\n",
                    STYLE_WARNING
                )

    tv.bind("<<TreeviewSelect>>", on_instruction_selected, "+")

    # Launch trace building (and comparison).
    tk.task_manager.enqueue(co_trace_builder())

    tk.mainloop()
