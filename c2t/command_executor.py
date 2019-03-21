__all__ = [
    "DebugCommandExecutor"
]


class DebugCommandExecutor(dict):
    """ This class executes commands passed in the comments of the test source
file and sets names of tracked variables
    """

    def __init__(self, proxy, lineno):
        super(DebugCommandExecutor, self).__init__()
        self.proxy = proxy
        self.lineno = lineno
        self.dbg_obj = proxy["self"]
        self.executing = None
        self.executed = []

    def __getattr__(self, var_name):
        if self.executing == "ch":
            self.dbg_obj.ch_line2var[self.lineno].append(var_name)
        elif self.executing == "chc":
            self.dbg_obj.chc_line2var[self.lineno].append(var_name)
        else:
            print("warning: command '%s' has not attributes, line: %s" % (
                self.executing, self.lineno
            ))
        return var_name

    def __getitem__(self, command):
        try:
            exec_command = self.__getattribute__(command)
        except AttributeError:
            print("warning: command '%s' is not defined, line: %s" % (
                command, self.lineno
            ))
            return self.proxy[command]
        else:
            self.executing = command
            if command not in self.executed:
                self.executed.append(command)
                exec_command(self.lineno)
        return self

    # supported debugging commands:

    # set breakpoint for checking of `lineno` accordance
    def br(self, lineno):
        self.dbg_obj.set_br_by_line(lineno, self.dbg_obj.check_cb)

    # set breakpoint for cyclical checking of `lineno` accordance
    def brc(self, lineno):
        self.dbg_obj.set_br_by_line(lineno, self.dbg_obj.cycle_check_cb)

    # set breakpoint to end of test
    def bre(self, lineno):
        self.dbg_obj.set_br_by_line(lineno, self.dbg_obj.finish_cb)

    # set breakpoint for checking of `lineno` accordance and variables values
    # accordance
    def ch(self, lineno):
        self.dbg_obj.set_br_by_line(lineno, self.dbg_obj.check_vars_cb)

    # set breakpoint for cyclical checking of `lineno` accordance and variables
    # values accordance
    def chc(self, lineno):
        self.dbg_obj.set_br_by_line(lineno, self.dbg_obj.cycle_check_vars_cb)
