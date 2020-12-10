from tools import *


class SUBC_B_Test(MSP430Watcher):

    def on_br1(self):
        "br_1"
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()

    def on_br2(self):
        "br_2"
        self.dump_stack()
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()
        self.rsp.exit = True
