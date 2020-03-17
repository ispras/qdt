#!/usr/bin/python

# QEMU log viewer
from argparse import (
    ArgumentParser
)
from itertools import (
    count
)
from traceback import (
    print_exc
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
    pipeline,
    limit_stage,
    mlget as _
)
from six.moves import (
    zip as izip,
    range as xrange,
)
from collections import (
    deque
)

# less value = more info
DEBUG = 3

def is_trace(l):
    # Looks like Chain is a fast jump to already translated TB (searched in
    # the cache) using non constant address (e.g. from a guest register),
    # while linking is a redirection to constant address (e.g. from an
    # instruction code immediate value) by translated code patching.
    # Chain message is printed _each time_.
    # Hence it's a "Trace" record analog for trace reconstruction algorithm.
    # Grep for: lookup_tb_ptr
    return l[:6] == "Trace " or l[:6] == "Chain "

def is_linking(l):
    return l[:8] == "Linking "

def is_in_asm(l):
    return l[:3] == "IN:"

def is_in_asm_instr(l):
    return l[:2] == "0x"


class InInstr(object):

    first = False # (in TB), set externally

    def __init__(self, l):
        self.l = l = l.rstrip()
        parts = l.split(":")

        if len(parts) < 2:
            raise ValueError("No `:` separator")

        self.addr = int(parts[0], base = 16)

        self.disas = ":".join(parts[1:])
        self.size = 1

    def __str__(self):
        return self.l


class TraceInstr(object):
    "Instruction with runtime (trace) information."

    # This also prevents erroneous attempts to use objects of this class as
    # objects of InInstr (i.e. foreign attribute setting).
    __slots__ = (
        "in_instr",
        "trace",
    )

    def __init__(self, in_instr, trace):
        self.in_instr = in_instr
        self.trace = trace

    # Proxify static info.

    def __getattr__(self, name):
        return getattr(self.in_instr, name)

    def __str__(self):
        return str(self.in_instr)


class TBCache(object):
    def __init__(self, back):
        self.map = {}
        self.links = {}
        self.tbMap = {}
        self.back = back

    def lookTBDown(self, addr):
        "Returns TB index and corresponding cache or None"
        c = self
        while c:
            if addr in c.tbMap:
                return (c.tbMap[addr], c)
            c = c.back
        return None

    def lookLinkDown(self, start_id):
        c = self
        while c:
            if start_id in c.links:
                return (c.links[start_id], c)
            c = c.back
        return None

    def lookInstrDown(self, addr):
        c = self
        while c:
            if addr in c.map:
                i = c.map[addr]
                if i.addr == addr:
                    return i, c
                # `addr` is not at the beginning of `i`. Hence, `i` probably
                # overwrites the instruction a caller looks for.
            c = c.back
        return None

    def commit(self, instr):
        m = self.map
        for addr in range(instr.addr, instr.addr + instr.size):
            m[addr] = instr

    def __contains__(self, instr):
        m = self.map
        for addr in range(instr.addr, instr.addr + instr.size):
            if addr in m:
                return True 

        return False


hexDigits = set("0123456789abcdefABCDEF")


class QTrace(object):

    def __init__(self, lines):
        self.header = header = lines[0].rstrip()

        l0 = iter(header)

        # Search for "CPU_LOG_EXEC" for trace message format.
        addrs = []
        for c in l0:
            if c == "[":
                break
        while True:
            addr = []
            for c in l0:
                if c in hexDigits:
                    addr.append(c)
                    break
            else:
                break
            for c in l0:
                if c in hexDigits:
                    addr.append(c)
                else:
                    break
            else:
                break
            try:
                addr_val = int("".join(addr), base = 16)
            except ValueError:
                continue
            addrs.append(addr_val)

        # `addrs[1]` is `pc`. Other values can represent different things
        # depending on Qemu version. They are not interesting here.
        try:
            self.firstAddr = addrs[1]
        except IndexError:
            self.bad = True

        if len(lines) > 1:
            self.cpuBefore = lines[1:]
        else:
            self.cpuBefore = None

        self.bad = False
        self.next = None

    def __str__(self):
        return self.header

    @property
    def as_text(self):
        cpu = self.cpuBefore
        if cpu is None:
            return self.header + "\n"
        else:
            return self.header + "\n" + "".join(cpu)


class EOL:
    "End Of Log"
    pass


class QEMULog(object):

    def __init__(self, file_name, limit = None):
        self.trace = []
        self.in_asm = []

        self.current_cache = TBCache(None)
        self.tbCounter = count(0)
        # across all caches
        # id -> (first addr, cache version)
        self.tbIdMap = {}

        self.prevTrace = None

        stages = [qlog_reader_stage(open(file_name, "r"))]
        if limit is not None:
            stages.append(limit_stage(limit))
        stages.append(self.feed())
        stages.append(self.trace_stage())

        self.pipeline = pipeline(*stages)

    def lookInstr(self, addr, fromCache = None):
        if fromCache is None:
            return self.current_cache.lookInstrDown(addr)
        elif fromCache == len(self.in_asm):
            return self.current_cache.lookInstrDown(addr)
        else:
            return self.in_asm[fromCache].lookInstrDown(addr)

    def lookLink(self, start_id, fromCache = None):
        if fromCache is None:
            return self.current_cache.lookLinkDown(start_id)
        elif fromCache == len(self.in_asm):
            return self.current_cache.lookLinkDown(start_id)
        else:
            return self.in_asm[fromCache].lookLinkDown(start_id)

    def trace_stage(self):
        traces_cache = deque()

        while True:
            while traces_cache:
                t = traces_cache.popleft()
                if not t.bad:
                    break
            else:
                while True:
                    t = yield
                    if not t.bad:
                        break

            if DEBUG < 2:
                print(t)

            addr = t.firstAddr
            instr = self.lookInstr(addr, t.cacheVersion)

            if instr is None:
                continue

            instr = instr[0]

            instr = TraceInstr(instr, t)

            tb = instr.tb

            # chain loop detection
            visitedTb = set([tb])

            while True:
                if DEBUG < 2:
                    print("0x%08X: %s" % (instr.addr, instr.disas))

                # Here we get next trace record from previous pipeline stage.
                # But we will handle it lately.
                traces_cache.append((yield instr))

                addr += instr.size

                nextInstr = self.lookInstr(addr, t.cacheVersion)

                nextTB = False

                if nextInstr is None:
                    nextTB = True
                else:
                    nextInstr = nextInstr[0]
                    if nextInstr.tb != tb:
                        nextTB = True

                if nextTB:
                    nextTbIdx = self.lookLink(tb, t.cacheVersion)
                    if nextTbIdx is None:
                        # chain is over
                        break

                    nextTbIdx = nextTbIdx[0]

                    if nextTbIdx in visitedTb:
                        if DEBUG < 2:
                            print("link loop %u -> ... -> %u" % (
                                nextTbIdx, tb
                            ))
                        break
                    else:
                        visitedTb.add(nextTbIdx)

                    if DEBUG < 2:
                        print("link %u -> %u" % (tb, nextTbIdx))

                    tb = nextTbIdx

                    addr = self.tbIdMap[tb][0]
                    nextInstr = self.lookInstr(addr, t.cacheVersion)

                    if nextInstr is None:
                        break

                    nextInstr = nextInstr[0]

                instr = nextInstr

    def cache_overwritten(self):
        cur = self.current_cache
        self.in_asm.append(cur)
        self.current_cache = TBCache(cur)

    def new_in_asm(self, in_asm):
        if DEBUG < 1:
            print("--- in_asm")
            print("".join(in_asm))

        tb = next(self.tbCounter)

        prev_instr = None
        for l in in_asm:
            try:
                instr = InInstr(l)
            except:
                print("Bad instruction: '%s'" % l.rstrip())
                print_exc()
                continue

            instr.tb = tb

            if prev_instr is None:
                self.current_cache.tbMap[instr.addr] = tb
                self.tbIdMap[tb] = (instr.addr, len(self.in_asm))
                instr.first = True

            if prev_instr:
                prev_instr.size = instr.addr - prev_instr.addr

            prev_instr = instr

            if instr in self.current_cache:
                self.cache_overwritten()

            self.current_cache.commit(instr)

    def new_trace(self, trace):
        if DEBUG < 1:
            print("--- trace")
            print("".join(trace))

        t = QTrace(trace)
        t.cacheVersion = len(self.in_asm)

        t.prev = self.prevTrace
        if self.prevTrace is not None:
            self.prevTrace.next = t

        self.prevTrace = t

        self.trace.append(t)

        return t

    def new_linking(self, linking):
        if DEBUG < 1:
            print("--- linking")

        self.cache_overwritten()

        try:
            parts = linking.split("[")
            start_part = parts[1]
            start_addr = start_part[0:start_part.index("]")]
            end_part = parts[2]
            end_addr = end_part[0:end_part.index("]")]
            start = int(start_addr, base = 16)
            end = int(end_addr, base = 16)

            c = self.current_cache
            start_tb = c.lookTBDown(start)
            end_tb = c.lookTBDown(end)
        except:
            print("linking bad: " + linking)
            print_exc()
            return

        if start_tb is None:
            print("linking bad: " + linking)
            print("Start " + start_tb + " TB is not found")
            return

        if end_tb is None:
            print("linking bad: " + linking)
            print("End " + end_tb + " TB is not found")
            return

        c.links[start_tb[0]] = end_tb[0]
        if DEBUG < 1:
            print("%x:%u -> %x:%u" % (start, start_tb[0], end, end_tb[0]))

    def new_unrecognized(self, l, lineno):
        l = l.rstrip()
        if l:
            print("--- new_unrecognized line %d" % lineno)
            print(l)

    def feed(self):
        lineno = 1
        l0 = yield

        prev_trace = None

        while l0 is not EOL:
            if is_in_asm(l0):
                in_asm = []
                l1 = yield; lineno += 1 # Those operations are always together.
                while l1 is not EOL:
                    if is_in_asm_instr(l1):
                        in_asm.append(l1)
                    else:
                        l0 = l1 # try that line in other `if`s
                        break
                    l1 = yield; lineno += 1
                else:
                    l0 = l1

                self.new_in_asm(in_asm)
                continue

            if is_trace(l0):
                trace = [l0]

                l1 = yield prev_trace; lineno += 1
                # We should prev_trace = None here, but it will be
                # overwritten below unconditionally.

                while l1 is not EOL:
                    # Traces are following one by one.
                    # - User did not passed other flags to -d.
                    # - Qemu can cancel TB execution because of `exit_request`
                    # or `tcg_exit_req` after trace message has been printed.
                    if is_trace(l1) or is_linking(l1) or is_in_asm(l1):
                        l0 = l1
                        break
                    trace.append(l1)
                    l1 = yield; lineno += 1
                else:
                    l0 = l1

                prev_trace = self.new_trace(trace)
                continue

            if is_linking(l0):
                self.new_linking(l0)
                l0 = yield; lineno += 1
                continue

            self.new_unrecognized(l0, lineno)
            l0 = yield; lineno += 1

        # There is no problem to yield `None` but it's possible iff input
        # log has no trace records.
        yield prev_trace


def qlog_reader_stage(f):
    yield

    for line in f:
        yield line

    yield EOL


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

    tv.tag_configure("difference", background = "#FF0000")
    STYLE_DIFFERENCE = ("difference",)

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

        for qlog_idx, (qlog_instrs, trace_text) in enumerate(izip(
            all_instructions, qlog_trace_texts
        )):
            try:
                i = qlog_instrs[idx]
            except IndexError:
                continue

            trace_text.insert(END, args.qlog[qlog_idx] + "\n", STYLE_FILE)

            if isinstance(i, TraceInstr):
                trace_text.insert(END, i.trace.as_text)
            else:
                trace_text.insert(END, _("No CPU data").get() + "\n",
                    STYLE_WARNING
                )

    tv.bind("<<TreeviewSelect>>", on_instruction_selected, "+")

    # Launch trace building (and comparison).
    tk.task_manager.enqueue(co_trace_builder())

    tk.mainloop()
