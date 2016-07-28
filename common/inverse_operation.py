class UnimplementedInverseOperation(Exception):
    pass

"""
Composite operations should be divided in sequence of basic operations with
same identifier as sequence parameter.

refs:

http://legacy.python.org/workshops/1997-10/proceedings/zukowski.html


Life cycle:
                                    done = True
                backed_up = True     |
                          |          |
 __init__ --> __backup__ --> __do__ --> __undo__
           \                               .
 backed_up = False             ^           |
      done = False             `-----------'
                                     \
                                    done = False

"__init__" is called same time the operation is created during "stage"
(by Python).
"__backup__" is called once JUST before first call of "__do__" during "commit"
(including "do").

"""

class InverseOperation(object):
    def __init__(self, previous = None, sequence = None):
        self.prev = previous
        self.next = []
        self.seq = sequence
        self.backed_up = False
        self.done = False

    def __backup__(self):
        raise UnimplementedInverseOperation()

    def __do__(self):
        raise UnimplementedInverseOperation()

    def __undo__(self):
        raise UnimplementedInverseOperation()

    def __read_set__(self):
        raise UnimplementedInverseOperation()

    def __write_set__(self):
        raise UnimplementedInverseOperation()


class InitialOperationCall(Exception):
    pass

class InitialOperation(InverseOperation):
    def __init__(self):
        InverseOperation.__init__(self)
        self.done = True

    def __backup__(self):
        raise InitialOperationCall()

    def __do__(self):
        raise InitialOperationCall()

    def __undo__(self):
        raise InitialOperationCall()

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
        queue = []

        while True:
            if self.pos.done:
                queue.append(self.pos)

            cur = self.pos
            self.pos = cur.prev

            if including:
                if including == cur:
                    break
            else:
                break

        if queue:
            for p in queue:
                p.__undo__()
                p.done = False

    def can_undo(self):
        return bool(not self.pos == self.history.root)

    def do(self, index = 0):
        op = self.pos.next[index]
        self.pos = op

        self.commit()

    def can_do(self, index = 0):
        return bool(self.pos.next and index < len(self.pos.next))

    def stage(self, op_class, *op_args, **op_kwargs):
        op = op_class(
            *op_args,
            previous = self.pos,
            **op_kwargs
        )

        if self.pos in self.history.leafs:
            self.history.leafs.remove(self.pos)

        self.history.leafs.append(op)
        self.pos.next.insert(0, op)
        self.pos = op

        return op

    def commit(self, including = None):
        if not including:
            p = self.pos
        else:
            p = including

        queue = []
        while p:
            if not p.done:
                # TODO:  check read/write sets before
                # some operations could be skipped if not required
                queue.insert(0, p)
            p = p.prev

        if queue:
            for p in queue:
                if not p.backed_up:
                    p.__backup__()
                    p.backed_up = True
    
                p.__do__()
                p.done = True



