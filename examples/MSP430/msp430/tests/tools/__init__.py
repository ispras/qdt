__all__ = [
    "MSP430Watcher",
]

from debug import (
    RSPWatcher,
)
from pyrsp.utils import (
    hexdump,
)


class MSP430Watcher(RSPWatcher):
    "Generic class for all MSP430 asm level tests"

    def __init__(self, rsp, elf_file_name):
        rsp.verbose = True

        super(MSP430Watcher, self).__init__(rsp, elf_file_name)

    def dump_stack(self, start_offset = 0, end_offset = 2):
        stack_addr = int(self.rsp.r1, base = 16)
        print("stack_addr 0x%x" % stack_addr)
        start_addr = stack_addr + start_offset
        stack_data = self.rsp[start_addr : (stack_addr + end_offset)]
        print("stack data:\n" + hexdump(stack_data, start_addr))
