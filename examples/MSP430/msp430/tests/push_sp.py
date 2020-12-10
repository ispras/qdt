from tools import *


class PUSH_SP_Test(MSP430Watcher):

    def on_br1(self):
        "br_1"
        self.dump_stack(-2, 6)
        self.rsp.step_over_br()

    def on_br2(self):
        "br_2"
        self.dump_stack(-2, 6)
        self.rsp.exit = True
