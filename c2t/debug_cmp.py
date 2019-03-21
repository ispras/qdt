__all__ = [
    "DebugComparison"
]

from common import (
    same
)

MSG_FORMAT = __name__ + ":\x1b[31m error:\x1b[0m {msg}"


class DebugComparison(object):
    """ This class compares values of debugging variables and displays
comparison report
"""

    def __init__(self, cmp_queue, count):
        self.end = count
        self.cmp_queue = cmp_queue
        self._assembly = lambda x: ''.join(
            [
                "\n               {k} = {v} ".format(k = k, v = v)
                if i and not (i % 3) else "{k} = {v} ".format(k = k, v = v)
                for i, (k, v) in enumerate(x.items())
            ]
        )

    def _print_report(self, msg, dump):
        report = msg

        for k, v in dump.iteritems():
            e, d = v

            report += (
                "\n\n{dump} dump ({elf}):\n"
                "    Source code line number: {lineno}\n"
                "    Instruction address: {addr}\n".format(dump = k.upper(),
                    elf = e, lineno = d["lineno"], addr = d["addr"]
                ) +
                ("    Variables: {vars}\n".format(
                    vars = self._assembly(d["vars"])
                ) if "vars" in d else '') +
                "    Registers: {regs}".format(
                    regs = self._assembly(d["regs"])
                )
            )
        print(report)

    def dump_compare(self, dump):
        _, oracle_dump = dump["oracle"]
        _, target_dump = dump["target"]

        if oracle_dump["lineno"] != target_dump["lineno"]:
            msg = MSG_FORMAT.format(prog = __file__,
                msg = "branch instruction error, test: {test}".format(
                    test = dump.pop("test")
                )
            )
            self._print_report(msg, dump)
            return 1
        elif (    "vars" in oracle_dump
              and "vars" in target_dump
              and not same(oracle_dump["vars"], target_dump["vars"])
        ):
                msg = MSG_FORMAT.format(prog = __file__,
                    msg = "binary instruction error, test: {test}".format(
                        test = dump.pop("test")
                    )
                )
                self._print_report(msg, dump)
                return 1
        return 0

    def start(self):
        """ Start debug comparison """
        while True:
            if not self.end:
                break
            debug_dump = self.cmp_queue.get(block = True)
            if debug_dump == "CMP_EXIT":
                self.end -= 1
            elif "TEST_END" in debug_dump:
                print("{test}: OK".format(test = debug_dump["TEST_END"]))
            elif not self.dump_compare(debug_dump):
                continue
            else:
                raise RuntimeError
