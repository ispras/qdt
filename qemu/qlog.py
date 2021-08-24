__all__ = [
    "InInstr"
  , "LogStep"
      , "TraceInstr"
      , "LogInt"
  , "TBCache"
  , "QTrace"
  , "QEMULog"
]


from itertools import (
    count
)
from common import (
    lazy,
    pipeline,
    limit_stage,
    ee
)
from traceback import (
    print_exc
)
from re import (
    compile,
)


# less value = more info
DEBUG = ee("QLOG_DEBUG", "3")

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

def is_trace_skipped(l):
    return l.startswith("Stopped execution of TB chain before 0x")

# Hint, grep Qemu sources for CPU_LOG_INT or (sometimes) CPU_LOG_TB_IN_ASM.
re_interrupt = compile(
    "((Servicing hardware INT)|(SMM: )|(check_exception)|( *\\d+: v=)).+"
)

def is_interrupt(l):
    return re_interrupt.match(l)

def is_cpu_restore(l):
    return l.startswith("TB exited at ")


re_space = compile("\\s+")
simple_byte_hex = "%02x".__mod__

class InInstr(object):

    first = False # (in TB), set externally

    def __init__(self, l):
        self.l = l = l.rstrip()
        parts = l.split(":")

        if len(parts) < 2:
            raise ValueError("No `:` separator")

        self.addr = int(parts[0], base = 16)

        self.disas = disas = ":".join(parts[1:]).strip()
        words_iter = iter(re_space.split(disas))

        bytes_ = []

        while True: # not a loop: a block with many exits
            for w in words_iter:
                # some instructions are hex-like (e.g.: x86 addb)
                if len(w) != 2:
                    opcode = w
                    break

                try:
                    b = int(w, base = 16)
                except ValueError:
                    opcode = w
                    break

                bytes_.append(b)
            else:
                opcode = None
                break

            for w in words_iter:
                opcode += " " + w

            break

        if bytes_:
            self.bytes = tuple(bytes_)
            self.size = len(bytes_)
        else:
            self.bytes = None
            self.size = None
            if not opcode:
                raise ValueError("Neither bytes nor opcode: '%s'" % l)

        self.opcode =  opcode

    def __str__(self):
        bytes_ = self.bytes
        if bytes_:
            return ("%-40s" % (self.opcode or "[no opcode]")
                +  " ".join(map(simple_byte_hex, self.bytes))
            )
        else:
            # Note, an opcode must be provided.
            return "%-40s" % self.opcode


class LogStep(object):
    "It's an execution trace step"

    __slots__ = (
        "icount",
        "difference",
    )

    def __init__(self):
        self.difference = None


class TraceInstr(LogStep):
    """ It's an execution of an in_asm instruction in TB (InInstr).
It can have runtime (trace) information.
    """

    # This also prevents erroneous attempts to use objects of this class as
    # objects of InInstr (i.e. foreign attribute setting).
    __slots__ = (
        "in_instr",
        "trace",
    )

    def __init__(self, in_instr, trace, icount):
        super(TraceInstr, self).__init__()

        self.in_instr = in_instr
        self.trace = trace
        self.icount = icount

    # Proxify static info.

    def __getattr__(self, name):
        return getattr(self.in_instr, name)

    def __str__(self):
        return str(self.in_instr)


class LogInt(LogStep):
    "It's interrupt/exception handling."

    __slots__ = (
        "header",
        "cpu_before",
        "lineno",
    )

    # It's always "good" unlike `QTrace`. See `QEMULog.trace_stage`.
    bad = False

    def __init__(self, lines, lineno):
        super(LogInt, self).__init__()

        self.header = lines[0].rstrip()
        if len(lines) > 1:
            self.cpu_before = lines[1:]
        else:
            self.cpu_before = None

        self.lineno = lineno

    def __str__(self):
        return self.header

    @property
    def as_text(self):
        cpu = self.cpu_before
        if cpu is None:
            return self.header + "\n"
        else:
            return self.header + "\n" + "".join(cpu)


class CPURestoreFromTB(object):

    # Tt's always "good" unlike `QTrace`. See `QEMULog.trace_stage`.
    bad = False

    def __init__(self, line, lineno):
        self.line = line
        self.lineno = lineno
        self.i = int(line[13:].rstrip())


class undefined: pass

class TBCache(object):

    def __init__(self, back):
        self.map = {}
        self.links = {}
        self.tbMap = {}
        self.back = back

        # remembers resolutions by `back` reference
        self.back_map_lookup_cache = {}

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
        upper_mlc = None
        mlc = None

        c = self
        while c:
            i = c.map.get(addr, None)
            # `addr` is not at the beginning of `i`. Hence, `i` probably
            # overwrites the instruction a caller looks for.
            if i is not None and i.addr == addr:
                res = (i, c)
                if upper_mlc is not None:
                    upper_mlc[addr] = res
                return res

            upper_mlc = mlc

            mlc = c.back_map_lookup_cache
            res = mlc.get(addr, undefined)
            if res is not undefined:
                if upper_mlc is not None:
                    upper_mlc[addr] = res
                return res

            c = c.back

        # Backing caches are considered constant.
        # So, we can remember misses in too.
        self.back_map_lookup_cache[addr] = None
        return None

    def commit(self, instr):
        m = self.map
        for addr in range(instr.addr, instr.addr + instr.size):
            m[addr] = instr

    def overlaps(self, addr, size):
        m = self.map
        for addr in range(addr, addr + size):
            if addr in m:
                return True

        return False


hexDigits = set("0123456789abcdefABCDEF")

# Record/Replay #2 adds line IC=[instructions_executed] to CPU state for
# debug.
re_instruction_counter = compile(".*IC=(\d+).*")


class QTrace(object):

    def __init__(self, lines, lineno):
        self.header = header = lines[0].rstrip()
        self.lineno = lineno

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

    @lazy
    def instruction_counter(self):
        cpu = self.cpuBefore

        if cpu is None:
            return None

        for l in cpu:
            match = re_instruction_counter.match(l)
            if match:
                return int(match.group(1))


class EOL:
    "End Of Log"
    pass

EMPTY = tuple()

class QEMULog(object):

    def __init__(self, file_name, limit = None):
        self.file_name = file_name
        self.trace = []
        self.in_asm = []

        self.current_cache = TBCache(None)
        self.tbCounter = count(0)
        # across all caches
        # id -> (first addr, cache version)
        self.tbIdMap = {}

        self.max_linked_tb = -1

        self.prevTrace = None

        stages = [qlog_reader_stage(open(file_name, "r"))]
        if limit is not None:
            stages.append(limit_stage(limit))
        stages.append(self.feed())
        stages.append(self.trace_stage())

        self.pipeline = pipeline(*stages)

    def iter_instructions(self):
        for chunk in self.pipeline:
            for i in chunk:
                yield i

    def lookInstr(self, addr, fromCache = None):
        if fromCache is None:
            return self.current_cache.lookInstrDown(addr)
        elif fromCache == len(self.in_asm):
            return self.current_cache.lookInstrDown(addr)
        else:
            return self.in_asm[fromCache].lookInstrDown(addr)

    def lookLink(self, start_id, fromCache = None):
        if start_id > self.max_linked_tb:
            return None

        if fromCache is None:
            return self.current_cache.lookLinkDown(start_id)
        elif fromCache == len(self.in_asm):
            return self.current_cache.lookLinkDown(start_id)
        else:
            return self.in_asm[fromCache].lookLinkDown(start_id)

    def trace_stage(self):
        ready = []
        instrs = []
        interrupts = []

        next_icount = 0

        while True:
            if ready:
                t = (yield ready)
                ready = []
            else:
                t = (yield EMPTY)
            while t.bad:
                t = (yield EMPTY)

            if DEBUG < 2:
                print(t)

            if isinstance(t, CPURestoreFromTB):
                i = t.i
                next_icount = instrs[i].icount

                # All interrupts are inserted after last executed instruction
                # of longjump-ed out TB.
                for interrupt in interrupts:
                    interrupt.icount = next_icount

                # If the `instr`uction caused CPU restore, it's not
                # executed (caused an exception).
                # So, next_icount is not incremented.
                # But the `instr`uction is yielded as an exception cause.
                ready.extend(instrs[:i + 1])
                instrs = []
                continue

            if isinstance(t, LogInt):
                t.icount = next_icount
                interrupts.append(t)
                continue

            # isinstance(t, QTrace), i.e. next trace record
            ready.extend(instrs)
            instrs = []
            ready.extend(interrupts)
            interrupts = []

            addr = t.firstAddr
            instr = self.lookInstr(addr, t.cacheVersion)

            if instr is not None:
                instr = instr[0]

                instr = TraceInstr(instr, t, next_icount)
                next_icount += 1

                tb = instr.tb
                tb_cache_version = self.tbIdMap[tb][1]

                # chain loop detection
                visitedTb = set([tb])

                while True:
                    if DEBUG < 2:
                        print("0x%08X: %s" % (instr.addr, instr.disas))

                    instrs.append(instr)

                    addr += instr.size

                    # A TB can be overlapped but still alive.
                    # The TB cannot jump to overlapping TB until end.
                    # So, we must use cache version of the TB to lookup next
                    # instruction of current TB instead of instruction copy
                    # from overlapping TB.
                    nextInstr = self.lookInstr(addr, tb_cache_version)

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

                        addr, tb_cache_version = self.tbIdMap[tb]
                        nextInstr = self.lookInstr(addr, tb_cache_version)

                        if nextInstr is None:
                            break

                        nextInstr = nextInstr[0]

                    instr = TraceInstr(nextInstr, None, next_icount)
                    next_icount += 1

    def cache_overwritten(self):
        cur = self.current_cache
        self.in_asm.append(cur)
        self.current_cache = TBCache(cur)

    def new_int(self, lines, lineno):
        if DEBUG < 1:
            print("".join(["--- interrupt\n"] + lines))

        return LogInt(lines, lineno)

    def new_cpu_restore(self, line, lineno):
        if DEBUG < 1:
            print("--- CPU restore form TB\n" + line)

        return CPURestoreFromTB(line, lineno)

    def new_in_asm(self, in_asm):
        if DEBUG < 1:
            print("--- in_asm")
            print("".join(in_asm))

        tb = next(self.tbCounter)

        # cache reference
        commit_instr = self.commit_instr

        prev_instr = None
        for l in in_asm:
            try:
                instr = InInstr(l)
            except:
                print("Bad instruction: '%s'" % l.rstrip())
                print_exc()
                continue

            if not instr.opcode:
                if prev_instr is None:
                    raise RuntimeError(
                        "in_asm record starts with an instruction tail:\n" +
                        "\n".join(in_asm) + "\n"
                    )
                if DEBUG < 3:
                    print("Join multiline instruction '%s' + '%s'" % (
                        prev_instr, instr
                    ))
                prev_instr.bytes += instr.bytes
                prev_instr.size += instr.size
                prev_instr.l += "\n" + instr.l
            else:
                instr.tb = tb

                if prev_instr is None:
                    instr.first = True
                else:
                    # Some QEMU disassembler implementations do not provide
                    # bytes of instructions.
                    if prev_instr.size is None:
                        prev_instr.size = instr.addr - prev_instr.addr

                    commit_instr(prev_instr, tb)

                prev_instr = instr

        if prev_instr is None:
            # All instructions are bad or in_asm is empty?
            return

        if prev_instr.size is None:
            # TODO: how to get it if disassembler did not provide bytes?
            prev_instr.size = 1

        commit_instr(prev_instr, tb)

    def commit_instr(self, instr, tb):
        cache = self.current_cache
        if cache.overlaps(instr.addr, instr.size):
            self.cache_overwritten()
            cache = self.current_cache

            # if at least one instruction of a TB overlaps another TB,
            # the overlapping TB becomes related to new cache version.
            if not instr.first:
                self.tbIdMap[tb][1] = len(self.in_asm)

        if instr.first:
            self.tbIdMap[tb] = [instr.addr, len(self.in_asm)]

            # It looks like, only first byte of an instruction is
            # really needed to be accounted in tbMap.
            cache.tbMap[instr.addr] = tb

        cache.commit(instr)

    def new_trace(self, trace, lineno):
        if DEBUG < 1:
            print("--- trace")
            print("".join(trace))

        if is_trace_skipped(trace[-1]):
            addr = trace[-1][37:].split()[0]
            if addr in trace[0]:
                if DEBUG < 2:
                    print("Skipping not executed trace at line %s:\n%s" % (
                        lineno, "".join(trace)
                    ))
                return None
            elif DEBUG < 3:
                # We don't skip the trace because at least one TB is executed.
                # Getting really executed TB's is an interesting problem...
                # Don't use linking (not chaining) if you want a precise log.
                # The situation is a corner case, so print it in less verbose
                # debug mode too.
                print("TB chain with skipped tail at line " + str(lineno))

        t = QTrace(trace, lineno)
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

        link_start = start_tb[0]
        if link_start > self.max_linked_tb:
            self.max_linked_tb = link_start

        c.links[link_start] = end_tb[0]
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

        to_yield = None

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
                trace_lineno = lineno

                # Note, there is no problem to yield `None` if a trace has been
                # skipped (see `new_trace`).
                l1 = yield to_yield; lineno += 1
                # We should to_yield = None here, but it will be
                # overwritten below unconditionally.

                while l1 is not EOL:
                    # Traces are following one by one.
                    # - User did not passed other flags to -d.
                    # - Qemu can cancel TB execution because of `exit_request`
                    # or `tcg_exit_req` after trace message has been printed.
                    if is_trace(l1) or is_linking(l1) or is_in_asm(l1) \
                    or is_interrupt(l1) or is_cpu_restore(l1):
                        l0 = l1
                        break
                    trace.append(l1)
                    # Ensure that skip mark is always at end of trace.
                    if is_trace_skipped(l1):
                        l0 = yield; lineno += 1
                        break
                    l1 = yield; lineno += 1
                else:
                    l0 = l1

                to_yield = self.new_trace(trace, trace_lineno)
                continue

            if is_linking(l0):
                self.new_linking(l0)
                l0 = yield; lineno += 1
                continue

            if is_interrupt(l0):
                # Some interrupts have CPU state like traces.
                interrupt = [l0]
                interrupt_lineno = lineno

                l1 = yield to_yield; lineno += 1
                # We should to_yield = None here, but it will be
                # overwritten below unconditionally.

                while l1 is not EOL:
                    if is_trace(l1) or is_linking(l1) or is_in_asm(l1) \
                    or is_interrupt(l1) or is_cpu_restore(l1):
                        l0 = l1 # try that line in other `if`s
                        break
                    else:
                        interrupt.append(l1)
                    l1 = yield; lineno += 1
                else:
                    l0 = l1

                to_yield = self.new_int(interrupt, interrupt_lineno)
                continue

            if is_cpu_restore(l0):
                restore = self.new_cpu_restore(l0, lineno)

                l0 = yield to_yield; lineno += 1
                to_yield = None

                yield restore
                continue

            self.new_unrecognized(l0, lineno)
            l0 = yield; lineno += 1

        # There is no problem to yield `None` but it's possible iff input
        # log has no trace records.
        yield to_yield


def qlog_reader_stage(f):
    yield

    for line in f:
        yield line

    yield EOL

