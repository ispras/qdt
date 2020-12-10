from tools import *


class RRC_B_Indirect_Test(MSP430Watcher):

    def on_br1(self):
        "br_1"
        self.dump_stack()
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()
        self.rsp.exit = True
