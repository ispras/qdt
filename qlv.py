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
    EPS,
    ee,
    mlget as _
)
from six.moves import (
    zip as izip,
    range as xrange,
)
from qemu import (
    TraceInstr,
    LogInt,
    QEMULog
)
from time import (
    time,
)


# less value = more info
DEBUG = ee("QLOG_DEBUG", "3")
DEBUG_INST_TV = ee("QLOG_DEBUG_INSTRUCTIONS_TREE_VIEW", "False")


# Instructions Treeview styles
STYLE_DEFAULT = tuple()
STYLE_DIFFERENCE = ("difference",)
STYLE_FIRST = ("first",)
STYLE_INTERRUPT = ("interrupt",)

# Instructions tree view shows only few instructions in backend Tk Treeview.
# Showed instructions interval is called "window".
# The window is automatically shifted when necessary by adding/removing rows
# beyond the window.
# Currently 1024 instructions are showed to user.
TV_WINDOW_SIZE = 1 << 10

# TODO: If user see all showed instructions, scrolling does not works.
# For bigger displays we should either catch mouse wheel, arrow buttons and
# other scrolling commands, or automatically adapt window size.

TV_WINDOW_HALF = TV_WINDOW_SIZE >> 1

INSTR_ADDR_FMT = "0x%08X"

class InstructionsTreeview(VarTreeview, object):

    def __init__(self, master, **kw):
        kw["columns"] = [
            "addr",
            "size",
            "disas"
        ]

        # The widget adjusts view window after each scroll.
        # Outer scroll handler, if specified, called by the widget.
        self._outer_yscrollcommand = kw.pop("yscrollcommand", None)

        VarTreeview.__init__(self, master,
            yscrollcommand = self._yscrollcommand,
            **kw
        )

        self.heading("addr", text = _("Address"))
        self.heading("size", text = _("Size"))
        self.heading("disas", text = _("Disassembly"))
        self.column("#0", width = 10)
        self.column("addr", minwidth = 120, width = 120)
        self.column("size", minwidth = 30, width = 30)
        self.column("disas", width = 600)

        self.tag_configure(STYLE_FIRST[0], background = "#EEEEEE")
        self.tag_configure(STYLE_DIFFERENCE[0], background = "#FF0000")
        self.tag_configure(STYLE_INTERRUPT[0],
            background = "#444444",
            foreground = "#FFFFFF"
        )

        self._all_instructions = []

        self._window_start = 0

        self.bind("<Destroy>", self._on_destroy, "+")

        self._rows_visible = 0
        self.bind("<<TreeviewOpen>>", self._on_open_close, "+")
        self.bind("<<TreeviewClose>>", self._on_open_close, "+")

        if DEBUG_INST_TV:
            self.bind("<Key-F5>", self._on_key_f5, "+")

    @property
    def total_instructions(self):
        return len(self._all_instructions)

    def append_instructions(self, insts):
        self._all_instructions.extend(insts)
        self._fill_window()
        self.update_window_shift(100)
        self.do_yscrollcommand(100)

    def see_instruction(self, idx):
        # We trying to keep user view in the middle of the window
        shift = int(idx - TV_WINDOW_HALF - self._window_start)

        self._shift_window(shift)

        VarTreeview.yview(self, idx - self._window_start)
        # Previous command not always results in _yscrollcommand feedback.
        # But the feedback must always be passed to an outer observer.
        self.do_yscrollcommand(10)

    def config(self, *a, **kw):
        # intercept outer yscrollcommand callback
        self._outer_yscrollcommand = kw.pop(
            "yscrollcommand", self._outer_yscrollcommand
        )
        if a or kw:
            VarTreeview.config(*a, **kw)

    def _on_open_close(self, __):
        # The item is not actually opened/closed right now.
        self.after(1, self._update_rows_visible)

    def _update_rows_visible(self):
        root_children = self.get_children()

        opened = 0
        rows = len(root_children)

        stack = list(root_children)
        while stack:
            parent = stack.pop()
            # Note, self.item("", "open") returns false (which is incorrect
            # because root is always opened). As a result, this algorithm is
            # not so beautiful.
            if not self.item(parent, "open"):
                continue
            children = self.get_children(parent)
            if children:
                n_children = len(children)
                rows += n_children
                opened += n_children
                stack.extend(children)

        self._rows_visible = rows
        self._opened_rows = opened

    def _yscrollcommand(self, *__):
        self.do_yscrollcommand(10)
        self.update_window_shift(100)

    def yview(self, action, *values):
        if action == "moveto":
            f_total_insts = float(self.total_instructions)

            f_pos = float(values[0])
            target_inst = int(f_pos * f_total_insts)

            self.see_instruction(target_inst)
        elif DEBUG_INST_TV:
            # TODO: some scroll commands are not implemented yet
            print(action, *values)

    def update_window_shift(self, delay):
        try:
            self.__update_window_shift
        except AttributeError:
            self.__update_window_shift = self.after(delay,
                self._update_window_shift
            )
        # else: # already scheduled

    def do_yscrollcommand(self, delay):
        try:
            self.__do_yscrollcommand
        except AttributeError:
            self.__do_yscrollcommand = self.after(delay,
                self._do_yscrollcommand
            )
        # else: # already scheduled

    if DEBUG_INST_TV:
        def _on_key_f5(self, __):
            self.update_window_shift(1)

    def _on_destroy(self, __):
        try:
            self.after_cancel(self.__update_window_shift)
        except AttributeError:
            pass # it's ok, no update has been scheduled
        else:
            del self.__update_window_shift

        try:
            self.after_cancel(self.__do_yscrollcommand)
        except AttributeError:
            pass # it's ok, no yscrollcommand has been scheduled
        else:
            del self.__do_yscrollcommand

    def _fill_window(self):
        # We need real number of top level rows in the Treeview
        instrs_in_window = len(self.get_children())

        if instrs_in_window >= TV_WINDOW_SIZE:
            return

        # cache some values
        cur_start = self._window_start
        all_insts = self._all_instructions
        _insert = self._insert_step

        new_inst_idx = cur_start + instrs_in_window
        new_inst_limit = cur_start + TV_WINDOW_SIZE
        new_insts = all_insts[new_inst_idx:new_inst_limit]

        for inst in new_insts:
            _insert(inst)

        self._update_rows_visible()

    def _update_window_shift(self):
        # remove self `after` callback identifier
        del self.__update_window_shift

        # The window middle is moved to currently visible rows.

        f_scroll_start = float(VarTreeview.yview(self)[0])
        scroll_index = int(f_scroll_start * self._rows_visible)

        shift = scroll_index - TV_WINDOW_HALF
        if shift == 0:
            return

        cur_instr = self._window_start + scroll_index

        self._shift_window(shift)

        # User should see same instructions
        VarTreeview.yview(self, cur_instr - self._window_start)

    def _shift_window(self, shift):
        # cache some values
        cur_start = self._window_start
        all_insts = self._all_instructions

        # start must be within interval [0, {{inst. count} - TV_WINDOW_SIZE}]
        new_start = max(0,
            min(len(all_insts) - TV_WINDOW_SIZE, cur_start + shift)
        )
        if new_start == cur_start:
            return

        actual_shift = new_start - cur_start

        if DEBUG_INST_TV:
            print("Shifting window to %d (%d)" % (new_start, actual_shift))

        self._window_start = new_start

        current_items = self.get_children()

        _insert = self._insert_step

        if actual_shift > 0:
            self.delete(*current_items[:actual_shift])

            new_inst_limit = new_start + TV_WINDOW_SIZE
            # actual_shift can be bigger than window size (absolute value)
            new_inst_idx = new_inst_limit - min(TV_WINDOW_SIZE, actual_shift)
            new_insts = all_insts[new_inst_idx:new_inst_limit]

            for inst in new_insts:
                _insert(inst)
        else: # actual_shift < 0
            self.delete(*current_items[actual_shift:])

            new_inst_idx = new_start
            new_inst_limit = new_inst_idx + min(TV_WINDOW_SIZE, -actual_shift)
            new_insts = all_insts[new_inst_idx:new_inst_limit]

            for insert_index, inst in enumerate(new_insts):
                _insert(inst, insert_index = insert_index)

        self._update_rows_visible()

    def _do_yscrollcommand(self):
        del self.__do_yscrollcommand

        outer = self._outer_yscrollcommand
        if outer is not None:
            total = self.total_instructions
            if total == 0:
                start, end = "0.0", "1.0"
            else:
                back_start, back_end = VarTreeview.yview(self)
                f_back_start = float(back_start)
                f_back_end = float(back_end)

                f_total = float(total + self._opened_rows)
                window_start = self._window_start
                f_window_start = float(window_start)
                f_in_window = float(self._rows_visible)
                factor = f_in_window / f_total

                f_start = f_window_start / f_total + f_back_start * factor
                f_size = (f_back_end - f_back_start) * factor
                f_end = f_start + f_size

                start = str(f_start)
                end = str(f_end)

            outer(start, end)

    def _insert_step(self, step,
        insert_index = "end"
    ):
        iid = self._insert_step_ignore_diff("", insert_index, step, None)

        diff = step.difference
        if diff is not None:
            self._insert_step_ignore_diff(iid, END, diff, STYLE_DIFFERENCE)

        return iid

    def _insert_step_ignore_diff(self, parent, insert_index, step, tags):
        if isinstance(step, TraceInstr):
            return self._insert_instruction_row(parent, insert_index, step,
                tags
            )
        elif isinstance(step, LogInt):
            return self._insert_interrupt_row(parent, insert_index, step,
                tags
            )
        else:
            tags = STYLE_DEFAULT if tags is None else tags
            return self.insert(parent, insert_index,
                text = str(step.icount),
                tags = tags,
                values = ("-", "-", str(step))
            )

    def _insert_interrupt_row(self, parent, insert_index, interrupt, tags):
        if tags is None:
            tags = STYLE_INTERRUPT

        return self.insert(parent, insert_index,
            text = str(interrupt.icount),
            tags = tags,
            values = ("-", "-", str(interrupt))
        )

    def _insert_instruction_row(self, parent, insert_index, inst, tags):
        if tags is None:
            tags = STYLE_FIRST if inst.first else STYLE_DEFAULT

        return self.insert(parent, insert_index,
            text = str(inst.icount),
            tags = tags,
            values = (INSTR_ADDR_FMT % inst.addr, "-", str(inst))
        )

    @property
    def selected_step_index(self):
        sel = self.selection()
        if not sel:
            return None

        iid = sel[0]
        parent = self.parent(iid)
        while parent: # != ""
            iid = parent
            parent = self.parent(iid)

        idx = self.index(iid)
        return idx + self._window_start


# Trace text (CPU state) styles.
STYLE_FILE = ("file",)
STYLE_WARNING = ("warning",)
# STYLE_DIFFERENCE of InstructionsTreeview is also used

class QLVWindow(GUITk):

    def __init__(self):
        GUITk.__init__(self)

        self.title(_("QEmu Log Viewer"))

        hk = self.hk
        hk(self._hk_copy, 54, symbol = "C")

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

        self.inst_per_sec = EPS()
        self.var_inst_per_sec = var = IntVar(self)
        sb.right(var)
        sb.right(_("I/sec"))

        self.qlog_trace_texts = []

    def _hk_copy(self):
        w = self.hk.event.widget
        if w is self.tv_instructions:
            idx = self.tv_instructions.selected_step_index
            if idx is None:
                return
            for log in self.all_instructions:
                try:
                    step = log[idx]
                except IndexError:
                    continue
                break
            else:
                return

            text = str(step.icount) + " "

            if isinstance(step, TraceInstr):
                text += INSTR_ADDR_FMT % step.addr + " " + str(step)
            else: # LogInt or unsupported type
                text += str(step)

            self.clipboard_clear()
            self.clipboard_append(text)

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
        var_ips_n = self.var_inst_per_sec
        ips = self.inst_per_sec

        self.qlogs = qlogs

        # Instructions are kept in lists: one per qlog.
        # This is list of those lists.
        self.all_instructions = all_instructions = list(list() for __ in qlogs)
        main_log = all_instructions[0]

        trace_iters = list(qlog.iter_instructions() for qlog in qlogs)
        idx = 0

        # Instructions Per Yield.
        # Big values results in GUI freezing. Small values result in overhead.
        # Also note that real amount of processed instructions in all logs is
        # in `len(qlogs)` times more than IPY.
        IPY = 600 // len(qlogs)

        # show N different rows
        differences_to_show = 3 # + 1 = N

        while True:
            start_idx = idx
            end_idx = idx + IPY

            # This counter should correlate with var_inst_n which shows
            # amount of _displayed_ instructions. Not total amount in all logs.
            var_ips_n.set(int(ips() * IPY))

            # Build subtrace for first log and then try to compare it with
            # subtraces of rest logs.

            iter_of_iters = iter(trace_iters)

            subtrace = list(
                izip(xrange(start_idx, end_idx), next(iter_of_iters))
            )

            if not subtrace:
                print("Trace has been built")
                break

            main_log.extend(ii[1] for ii in subtrace)
            var_inst_n.set(len(main_log))

            difference = False

            for log_idx, qlog_iter_2 in enumerate(iter_of_iters, 1):
                i1_idx = start_idx - 1

                log_instrs = all_instructions[log_idx]

                for (i1_idx, i1), i2 in izip(subtrace, qlog_iter_2):
                    if difference:
                        if differences_to_show:
                            differences_to_show -= 1
                        else:
                            # `i1_idx`-th instruction is not compared actually
                            # (see `compared` evaluation below).
                            i1_idx -= 1
                            break

                    log_instrs.append(i2)

                    type_i1 = type(i1)

                    if type_i1 is not type(i2):
                        difference = True
                        i1.difference = i2
                        continue

                    if issubclass(type_i1, TraceInstr):
                        # Currently, comparison is address based only.
                        if i1.addr != i2.addr:
                            difference = True
                            i1.difference = i2
                            continue

                compared = i1_idx - start_idx + 1
                if compared < len(subtrace):
                    # Log 2 ended earlier.
                    subtrace = subtrace[:compared]

                if not differences_to_show:
                    break

            if not subtrace:
                print("Trace has been built")
                break

            tv.append_instructions(ii[1] for ii in subtrace)
            var_inst_n.set(tv.total_instructions)

            if DEBUG < 3:
                for i in iter(ii[1] for ii in subtrace):
                    if isinstance(i, TraceInstr):
                        print("0x%08X: %s" % (i.addr, i.disas))
                    else:
                        print(i) # use default `__str__`

            idx = subtrace[-1][0] + 1

            if difference:
                # idx does always point to an instruction with difference,
                # because it's last in `subtrace`.
                tv.see_instruction(idx)
                print("Difference found, stopping")
                break

            # No more instructions in the trace
            if idx < end_idx:
                print("Trace has been built")
                break

            yield True

        t2 = time()
        print("In %f second(s)" % (t2 - t1))

    def _on_instruction_selected(self, __):
        qlog_trace_texts = self.qlog_trace_texts
        qlogs = self.qlogs

        for trace_text in qlog_trace_texts:
            trace_text.delete("1.0", END)

        idx = self.tv_instructions.selected_step_index
        if idx is None:
            return

        left_text = None

        for qlog_idx, (qlog_instrs, trace_text) in enumerate(izip(
            self.all_instructions, qlog_trace_texts
        )):
            try:
                i = qlog_instrs[idx]
            except IndexError:
                continue

            file_name = qlogs[qlog_idx].file_name

            if isinstance(i, TraceInstr):
                trace = i.trace
                if trace is None:
                    file_pos = file_name + "\n"
                else:
                    file_pos = "%s:%d\n" % (file_name, trace.lineno)

                trace_text.insert(END, file_pos, STYLE_FILE)

                if trace is None:
                    trace_text.insert(END, _("No CPU data").get() + "\n",
                        STYLE_WARNING
                    )
                else:
                    if qlog_idx == 0:
                        left_text = trace.as_text
                        trace_text.insert(END, left_text)
                    else:
                        cur_trace = trace.as_text
                        if left_text is None:
                            # Left log has no trace record for this
                            # instruction. Nothing to diff.
                            trace_text.insert(END, cur_trace)
                        else:
                            insert_diff(trace_text, left_text, cur_trace)

            elif isinstance(i, LogInt):
                file_pos = "%s:%d\n" % (file_name, i.lineno)
                trace_text.insert(END, file_pos, STYLE_FILE)

                cpu = i.cpu_before
                if cpu is None:
                    trace_text.insert(END, _("No CPU data").get() + "\n",
                        STYLE_WARNING
                    )
                else:
                    if qlog_idx == 0:
                        left_text = "".join(cpu)
                        trace_text.insert(END, left_text)
                    else:
                        cur_trace = "".join(cpu)
                        if left_text is None:
                            # Left log has no CPU state for this interrupt.
                            # Nothing to diff.
                            trace_text.insert(END, cur_trace)
                        else:
                            insert_diff(trace_text, left_text, cur_trace)
            else:
                trace_text.insert(END,
                    (_("Unsupported step type %s") % type(i).__name__).get()
                )


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
