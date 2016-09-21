from common import \
    HistoryTracker, \
    InverseOperation

class ProjectOperation(InverseOperation):
    def __init__(self, project, *args, **kw):
        InverseOperation.__init__(self, *args, **kw)

        self.p = project

    """
    The InverseOperation defines no read or write sets. Instead it raises an
    exception. As this is a base class of all machine editing operations it
    should define the sets. The content of the sets is to be defined by
    subclasses.
    """

    def __write_set__(self):
        return []

    def __read_set__(self):
        return []


class ProjectHistoryTracker(HistoryTracker):
    def __init__(self, project, *args, **kw):
        HistoryTracker.__init__(self, *args, **kw)
        self.p = project

    def stage(self, op_class, *op_args, **op_kw):
        return HistoryTracker.stage(self,
            op_class,
            *(op_args + (self.p,)), **op_kw
        )
