from tools import *


class PUSH_Auto_Inc_Test(MSP430Watcher):

    def on_br1(self):
        "br_1"
        self.dump_stack(-2, 2)
        # registers will be printed by RSP in verbose mode
        self.rsp.step_over_br()
        self.rsp.exit = True
