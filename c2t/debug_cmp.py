__all__ = [
    "DebugComparator"
  , "TestError"
      , "TestTimeout"
      , "TestMismatch"
]

from collections import (
    OrderedDict,
    defaultdict,
    deque
)
from six.moves.queue import (
    Empty
)
from common import (
    same
)
from .test_log import (
    TestLog,
)

MSG_FORMAT = __name__ + ":\x1b[31m error:\x1b[0m {msg}"


class DebugComparator(object):
    """ This class compares values of debugging variables and displays
comparison report
    """

    def __init__(self, dump_queue, count):
        self.end = count
        self.dump_queue = dump_queue
        self.test2logs = defaultdict(TestLog)

    @staticmethod
    def _format_variables(_vars):
        for n, v in _vars.items():
            yield "{n} = {v} (0x{v:x})".format(n = n, v = v)

    @staticmethod
    def _format_rows(records, columns = 3):
        for i, r in enumerate(records):
            if i:
                if i % columns:
                    yield " "
                else:
                    yield "\n               "
            yield r

    @staticmethod
    def _prepare_vars4print(_vars):
        return "".join(
            DebugComparator._format_rows(
                DebugComparator._format_variables(_vars),
                columns = 2
            )
        )

    @staticmethod
    def _prepare_regs4print(regs):
        return "".join(
            DebugComparator._format_rows(
                map("%s = %s".__mod__, regs.items())
            )
        )

    def _format_report(self, msg, dump):
        report = msg

        for key, val in dump.items():
            report += (
                "\n\n{dump} dump ({elf}):\n"
                "    Source code line number: {lineno}\n"
                "    Instruction address: {addr}\n".format(
                    dump = key.upper(),
                    elf = val["elf"],
                    lineno = val["lineno"],
                    addr = val["addr"]
                ) + ("    Variables: {vars}\n".format(
                    vars = self._prepare_vars4print(val["vars"])
                ) if "vars" in val else '') + "    Registers: {regs}".format(
                    regs = self._prepare_regs4print(val["regs"])
                )
            )
        return report

    def _print_report(self, *a, **kw):
        print(self._format_report(*a, **kw))

    def compare(self, test, sender, dump, cmp_sender, cmp_dump):
        if dump["lineno"] != cmp_dump["lineno"]:
            msg = MSG_FORMAT.format(
                msg = "branch instruction error"
            )
        elif (    "vars" in dump
              and "vars" in cmp_dump
              and not same(dump["vars"], cmp_dump["vars"])
        ):
            msg = MSG_FORMAT.format(
                msg = "binary instruction error"
            )
        else:
            return

        dump4report = OrderedDict(
            sorted({sender: dump, cmp_sender: cmp_dump}.items(),
                key = lambda x: x
            )
        )
        yield TestMismatch(test, self._format_report(msg, dump4report))

    def start(self):
        """ Start debug comparison """
        oracle_dump_cache = defaultdict(deque)
        target_dump_cache = defaultdict(deque)

        while self.end:
            try:
                sender, test, dump = self.dump_queue.get(timeout = 0.1)
            except Empty:
                continue

            # TODO: sender (debugger) should also provide a timestamp of the
            #       moment the dump has been gotten
            if test is not None:
                # Do not log system events like "TEST_EXIT"
                self.test2logs[test].log(sender, dump)

            if dump == "TEST_TIMEOUT":
                yield TestTimeout(test)
                continue

            if sender == "oracle":
                if test in target_dump_cache and target_dump_cache[test]:
                    cmp_sender = "target"
                    cmp_dump = target_dump_cache[test].popleft()
                else:
                    oracle_dump_cache[test].append(dump)
                    continue
            elif sender == "target":
                if test in oracle_dump_cache and oracle_dump_cache[test]:
                    cmp_sender = "oracle"
                    cmp_dump = oracle_dump_cache[test].popleft()
                else:
                    target_dump_cache[test].append(dump)
                    continue
            else:
                print(MSG_FORMAT.format(msg = "wrong sender"))
                raise RuntimeError

            if dump == "TEST_EXIT" and cmp_dump == "TEST_EXIT":
                self.end -= 1
            elif dump == "TEST_RUN" and cmp_dump == "TEST_RUN":
                print("%s: RUN" % test)
            elif dump == "TEST_END":
                if dump == cmp_dump:
                    print("%s: OK" % test)
                else:
                    yield TestMismatch(test, sender + " ended earlier")
            elif cmp_dump == "TEST_END":
                # dump != "TEST_END"
                yield TestMismatch(test, cmp_sender + " ended earlier")
            else:
                for res in self.compare(test, sender, dump, cmp_sender,
                    cmp_dump
                ):
                    yield res


class TestError(object):

    def __init__(self, test):
        self.test = test


class TestTimeout(TestError):

    def __str__(self):
        return self.test + ": TIMEOUT"


class TestMismatch(TestError):

    def __init__(self, test, report):
        super(TestMismatch, self).__init__(test)
        self.report = report

    def __str__(self):
        return self.test + ":\n" + self.report
