from tools import *


class PUSH_B_CG_Test(MSP430Watcher):

    def on_br1(self):
        "br_1"
        self.dump_stack(end_offset = 12)
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()
        self.rsp.exit = True
