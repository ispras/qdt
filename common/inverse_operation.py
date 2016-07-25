class UnimplementedInverseOperation(Exception):
    pass

"""
Composite operations should be divided in sequence of basic operations with
same identifier as sequence parameter.

refs:

http://legacy.python.org/workshops/1997-10/proceedings/zukowski.html
"""

class InverseOperation(object):
    def __init__(self, previous = None, sequence = None):
        self.prev = previous
        self.next = []
        self.seq = sequence

    def __do__(self):
        raise UnimplementedInverseOperation()

    def __undo__(self):
        raise UnimplementedInverseOperation()

    def __read_set__(self):
        raise UnimplementedInverseOperation()

    def __write_set__(self):
        raise UnimplementedInverseOperation()


class InitialOperationDoneOrUndone(Exception):
    pass

class InitialOperation(InverseOperation):
    def __init__(self):
        InverseOperation.__init__(self)

    def __do__(self):
        raise InitialOperationDoneOrUndone

    def __undo__(self):
        raise InitialOperationDoneOrUndone

    def __read_set__(self):
        return []

    def __write_set__(self):
        return []

class History(object):
    def __init__(self):
        self.root = InitialOperation()
        self.leafs = [self.root]

class HistoryTracker(object):
    def __init__(self, history):
        self.history = history
        self.pos = history.leafs[0]

    def undo(self, including = None):
        self.pos.__undo__()
        self.pos = self.pos.prev

        if including:
            if including == self.pos:
                self.undo()
            else:
                self.undo(including)

    def can_undo(self):
        return bool(not self.pos == self.history.root)

    def redo(self, index = 0):
        next = self.pos.next[index]
        next.__do__()
        self.pos = next

    def can_redo(self, index = 0):
        return bool(self.pos.next and index < len(self.pos.next))

    def commit(self, op_class, *op_args, **op_kwargs):
        op = op_class(
            *op_args,
            previous = self.pos,
            **op_kwargs
        )
        if self.pos in self.history.leafs:
            self.history.leafs.remove(self.pos)

        op.__do__()

        self.history.leafs.append(op)
        self.pos.next.insert(0, op)
        self.pos = op
