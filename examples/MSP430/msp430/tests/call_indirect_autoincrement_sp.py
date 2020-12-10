from tools import *


class CALL_Auto_Inc_Test(MSP430Watcher):

    def on_br1(self):
        "br_1"
        self.dump_stack(0, 6)
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()

    def on_br2(self):
        "br_2"
        self.dump_stack(-2, 4)
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()
        self.rsp.exit = True
