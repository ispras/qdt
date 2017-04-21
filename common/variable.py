__all__ = [ "Variable" ]

# Tk variable emulation class
# TODO: use Notifier for feedback

def undefined(): pass

class Variable(object):
    """ None as value is a value too. Hence use special internal symbol
    'undefined' to distinguish None-valued and non-provided keyword argument.
    """
    def __init__(self, value = undefined):
        self.__w = self.__changed = []
        self.__r = self.__going_read = []
        self.__u = self.__undefining = []

        if value is not undefined:
            self.__value = value

    def __del__(self):
        try:
            (self.__value)
        except AttributeError:
            # Variable was not defined. Hence, it is not being undefined there.
            return

        undefining = self.__undefining
        # freeze current list because callback can change it
        for cb in list(undefining):
            cb()

    def __set_internal(self, value):
        self.__value = value

        changed = self.__changed
        if changed:
            for cb in list(changed):
                cb()

    def set(self, value):
        try:
            cur_value = self.__value
        except AttributeError:
            self.__set_internal(value)
        else:
            if value is not cur_value and value != cur_value:
                self.__set_internal(value)

    def get(self):
        going_read = self.__going_read
        if going_read:
            for cb in list(going_read):
                cb()
        try:
            return self.__value
        except AttributeError:
            raise RuntimeError("Variable is referenced before assignment.")

    def trace_variable(self, mode, callback):
        getattr(self, "_Variable__" + mode).append(callback)
        return (mode, callback)

    def trace_vdelete(self, mode, cbname):
        assert cbname[0] == mode
        getattr(self, "_Variable__" + mode).remove(cbname[1])
