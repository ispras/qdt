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
    GUITk,
    VarTreeview
)
from six.moves.tkinter import (
    Scrollbar
)
from six.moves.tkinter_ttk import (
    Style
)
from common import (
    mlget as _
)
from six.moves import (
    zip as izip,
    range as xrange,
)

# less value = more info
DEBUG = 3

def is_trace(l):
    return l[:6] == "Trace "

def is_linking(l):
    return l[:8] == "Linking "

def is_in_asm(l):
    return l[:3] == "IN:"

def is_in_asm_instr(l):
    return l[:2] == "0x"


class InInstr(object):

    def __init__(self, l):
        l = l.rstrip()
        parts = l.split(":")

        if len(parts) < 2:
            raise ValueError("No `:` separator")

        self.addr = int(parts[0], base = 16)

        self.disas = ":".join(parts[1:])
        self.size = 1


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
        l0 = iter(lines[0])

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


class EOL:
    "End Of Log"
    pass


class QEMULog(object):

    def __init__(self):
        self.trace = []
        self.in_asm = []

        self.current_cache = TBCache(None)
        self.tbCounter = count(0)
        # across all caches
        # id -> (first addr, cache version)
        self.tbIdMap = {}

        self.prevTrace = None

        self.feeder = self.feed()
        next(self.feeder)

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

    def full_trace(self):
        if not self.trace:
            return []

        titer = iter(self.trace)

        for t in titer:
            if not t.bad:
                break
        else:
            return []

        ret = []

        while t:
            for nextT in titer:
                if not nextT.bad:
                    break
            else:
                nextT = None

            addr = t.firstAddr
            instr = self.lookInstr(addr, t.cacheVersion)

            if instr is None:
                t = nextT
                continue

            instr = instr[0]

            tb = instr.tb

            # chain loop detection
            visitedTb = set([tb])

            while True:
                if DEBUG < 2:
                    print("0x%08X: %s" % (instr.addr, instr.disas))

                ret.append(instr)

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

            t = nextT

        return ret

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

                l1 = yield; lineno += 1
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

                self.new_trace(trace)
                continue

            if is_linking(l0):
                self.new_linking(l0)
                l0 = yield; lineno += 1
                continue

            self.new_unrecognized(l0, lineno)
            l0 = yield; lineno += 1

        # `StopIteration` should not be raised because `send` method is used
        # to input lines. Just ignore consequent input.
        while True:
            yield

    def feed_file(self, f):
        # iterate file line by line
        feeder = self.feeder
        for l in f:
            feeder.send(l)
        feeder.send(EOL)

    def feed_lines(self, f, limit = 1000):
        feeder = self.feeder
        for last, l in izip(xrange(limit), f):
            feeder.send(l)
        if last < limit - 1:
            feeder.send(EOL)

    def feed_file_by_name(self, file_name):
        f = open(file_name, "r")
        self.feed_file(f)
        f.close()


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
    ap.add_argument("qlog")

    args = ap.parse_args()

    qlogFN = args.qlog

    print("Reading " + qlogFN)

    qlog = QEMULog()
    with open(qlogFN, "r") as log_stream:
        qlog.feed_lines(log_stream, int(args.l))
    qlog.feeder.send(EOL)

    print("Building full trace")
    trace = qlog.full_trace()

    tk = GUITk()
    tk.title(_("QEmu Log Viewer"))
    tk.geometry("1000x600")
    tk.grid()
    tk.rowconfigure(0, weight = 1)
    tk.columnconfigure(0, weight = 1)
    tk.columnconfigure(1, weight = 0)

    tkstyle = Style()
    tkstyle.configure("Treeview", font = ("Courier", 10))

    columns = [
        "addr",
        "size",
        "disas"
    ]

    tv = VarTreeview(tk, columns = columns)
    tv.heading("addr", text = _("Address"))
    tv.heading("size", text = _("Size"))
    tv.heading("disas", text = _("Disassembly"))
    tv.column("#0", width = 10)
    tv.column("addr", minwidth = 120, width = 120)
    tv.column("size", minwidth = 30, width = 30)
    tv.column("disas", width = 600)
    tv.grid(row = 0, column = 0, sticky = "NESW")

    vscroll = Scrollbar(tk)
    vscroll.grid(row = 0, column = 1, sticky = "NS")

    tv.config(yscrollcommand = vscroll.set)
    vscroll.config(command = tv.yview)

    for idx, i in enumerate(trace):
        if DEBUG < 3:
            print("0x%08X: %s" % (i.addr, i.disas))
        tv.insert("", "end",
            text = str(idx),
            values = ("0x%08X" % i.addr, "-", str(i.disas))
        )

    tk.mainloop()
