from qemu import \
    ProjectHistoryTracker

class GUIProjectHistoryTracker(ProjectHistoryTracker):
    def __init__(self, *args, **kw):
        ProjectHistoryTracker.__init__(self, *args, **kw)

        self.operation_strings = {}

        for op in self.get_branch():
            self.on_operation(op)

        self.add_on_changed(self.on_operation)

        # use initial operation description as description of its sequence
        self.sequence_strings = {
            self.history.root.seq : self.operation_strings[self.history.root]
        }

    def on_operation(self, op):
        if op not in self.operation_strings:
            self.operation_strings[op] = op.__description__()

    def set_sequence_description(self, desc):
        self.sequence_strings[self.current_sequence] = desc

    def start_new_sequence(self, prev_seq_desc = None):
        if prev_seq_desc is not None:
            self.set_sequence_description(prev_seq_desc)

        ProjectHistoryTracker.start_new_sequence(self)

    def commit(self, *args, **kw):
        try:
            seq_desc = kw["sequence_description"]
        except KeyError:
            seq_desc = None
        else:
            del kw["sequence_description"]

        if seq_desc is not None:
            self.sequence_strings[self.current_sequence] = seq_desc

        ProjectHistoryTracker.commit(self, *args, **kw)
