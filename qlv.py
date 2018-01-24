#!/usr/bin/python

# QEMU log viewer
from argparse import ArgumentParser
from itertools import count
from traceback import print_exc
from widgets import (
    GUITk,
    VarTreeview
)
from six.moves.tkinter import (
    Scrollbar,
    YES
)
from common import mlget as _

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
            self.bad = True
            return

        try:
            self.addr = int(parts[0], base = 16)
        except ValueError:
            self.bad = True
            return

        self.disas = ":".join(parts[1:])
        self.size = 1
        self.bad = False

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
                if i.bad:
                    continue
                if i.addr != addr:
                    continue
                return i, c
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

        addr = []
        for c in l0:
            if c == "[":
                break
        for c in l0:
            if c == " ":
                break
        for c in l0:
            if c in hexDigits:
                addr.append(c)
            else:
                break

        try:
            self.firstAddr = int("".join(addr), base = 16)
        except ValueError:
            self.bad = True

        if len(lines) > 1:
            self.cpuBefore = lines[1:]
        else:
            self.cpuBefore = None

        self.bad = False
        self.next = None

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
            else:
                instr = instr[0]
                if instr.bad:
                    continue

            tb = instr.tb

            # chain loop detection
            visitedTb = set([tb])

            while True:
                if DEBUG < 2:
                    print("0x%08X: %s" % (instr.addr, instr.disas))

                if instr.addr == 0x00000186:
                    pass

                ret.append(instr)

                addr += instr.size

                nextInstr = self.lookInstr(addr, t.cacheVersion)

                nextTB = False

                if nextInstr is None:
                    nextTB = True
                else:
                    nextInstr = nextInstr[0]
                    if nextInstr.bad:
                        break
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
                            print("link loop %u -> ... -> %u" % (nextTbIdx, tb))
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
                    else:
                        nextInstr = nextInstr[0]
                        if nextInstr.bad:
                            break

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
            instr = InInstr(l)
            instr.tb = tb

            if instr.bad:
                prev_instr = instr
                print("Bad instruction: '%s'" % l.rstrip())
                continue

            if prev_instr is None:
                self.current_cache.tbMap[instr.addr] = tb
                self.tbIdMap[tb] = (instr.addr, len(self.in_asm))

            if prev_instr and not prev_instr.bad:
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

    def new_unrecognized(self, l):
        l = l.rstrip()
        if l:
            print("--- new_unrecognized line")
            print(l)

    def feed(self, reader):
        for l0 in reader:
            while l0 is not None:
                if is_in_asm(l0):
                    in_asm = []
                    for l1 in reader:
                        if is_in_asm_instr(l1):
                            in_asm.append(l1)
                        else:
                            l0 = l1
                            break
                    else:
                        l0 = None

                    self.new_in_asm(in_asm)
                    continue

                if is_trace(l0):
                    trace = [l0]

                    for l1 in reader:
                        if is_trace(l1) or is_linking(l1) or is_in_asm(l1):
                            l0 = l1
                            break
                        trace.append(l1)
                    else:
                        l0 = None

                    self.new_trace(trace)
                    continue

                if is_linking(l0):
                    self.new_linking(l0)
                    break

                self.new_unrecognized(l0)
                break

    def feed_file(self, f):
        self.feed(f.xreadlines())

    def feed_file_by_name(self, file_name):
        f = open(file_name, "r")
        self.feed_file(f)
        f.close()

if __name__ == "__main__":
    ap = ArgumentParser(
        prog = "QEMU Log Viewer"
    )
    ap.add_argument("qlog")

    args = ap.parse_args()

    qlogFN = args.qlog

    print("Reading " + qlogFN)

    qlog = QEMULog()
    qlog.feed_file_by_name(qlogFN)

    print("Building full trace")
    trace = qlog.full_trace()

    tk = GUITk()
    tk.title(_("QEmu Log Viewer"))
    tk.geometry("600x600")
    tk.grid()
    tk.rowconfigure(0, weight = 1)
    tk.columnconfigure(0, weight = 1)
    tk.columnconfigure(1, weight = 0)

    columns = [
        "size",
        "disas"
    ]

    tv = VarTreeview(tk, columns = columns)
    tv.heading("#0", text = _("Address"))
    tv.heading("size", text = _("Size"))
    tv.heading("disas", text = _("Disassembly"))
    tv.column("#0", minwidth = 120, width = 120)
    tv.column("size", minwidth = 30, width = 30)
    tv.column("disas", minwidth = 200)
    tv.grid(row = 0, column = 0, stick = "NESW")

    vscroll = Scrollbar(tk)
    vscroll.grid(row = 0, column = 1, sticky = "NS")

    tv.config(yscrollcommand = vscroll.set)
    vscroll.config(comman = tv.yview)

    for i in trace:
        if DEBUG < 3:
            print("0x%08X: %s" % (i.addr, i.disas))
        tv.insert("", "end",
            text = "0x%08X" % i.addr,
            values = ("-", str(i.disas))
        )

    tk.mainloop()
