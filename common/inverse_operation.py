__all__ = [
    "InverseOperation"
  , "InitialOperationBackwardIterator"
  , "UnimplementedInverseOperation"
  , "InitialOperationCall"
  , "History"
  , "HistoryTracker"
]

from six import integer_types

from six.moves import zip

from .ml import mlget as _

from .notifier import Notifier

class UnimplementedInverseOperation(NotImplementedError):
    pass

simple_eq_types = [
    bool,
    str,
    float
] + list(integer_types)

def set_touches_entry(X, e):
    for x in X:
        if isinstance(x, tuple):
            if isinstance(e, tuple):
                for ee, xx in zip(e, x):
                    if not ee == xx:
                        break
                else:
                    return True
            elif type(e) in simple_eq_types:
                if e == x[0]:
                    return True
            else:
                raise Exception("Unsupported type of entry: " + str(type(e)))
        elif type(x) in simple_eq_types:
            if isinstance(e, tuple):
                if e[0] == x:
                    return True
            elif e == x:
                return True
        else:
            Exception("Unsupported type of entry: " + str(type(x)))
    return False

"""
Composite operations should be divided in sequence of basic operations with
same identifier as sequence parameter.

refs:

http://legacy.python.org/workshops/1997-10/proceedings/zukowski.html


Life cycle:
                                   ___---> __description__
        / after first call \      /                ^
        \ to __do__ only]  / -->(!)                |
                                 |                 |   / all referenced   \
                                 |  done = True    |   | objects should   |
              backed_up = True   |   |             |   | be in same state |
                          |      |   |            (!)<-| as during first  |
 __init__ --> __backup__ --> __do__ --> __undo__   |   | call to __do__   |
           \                               .       |   | (use r/w sets    |
 backed_up = False             ^           |-------'   | to control this, |
      done = False             `-----------'           \ for instance)]   /
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

    def writes(self, entry):
        return set_touches_entry(self.__write_set__(), entry)

    def __description__(self):
        return _("Reversible operation with unimplemented description \
(class %s).") % type(self).__name__

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

    def __description__(self):
        return _("The beginning of known history.")

def InitialOperationBackwardIterator(cur):
    while cur is not None:
        yield cur
        cur = cur.prev

    raise StopIteration()

class History(object):
    def __init__(self):
        self.root = InitialOperation()
        self.leafs = [self.root]

@Notifier("changed")
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

                self.__notify_changed(p)

    def undo_sequence(self):
        cur = self.pos

        seq = cur.seq
        if seq is None:
            raise Exception("No sequence was defined")

        while True:
            prev = cur.prev
            if not prev.seq == seq:
                self.undo(cur)
                break
            cur = prev

    def can_undo(self):
        return bool(not self.pos == self.history.root)

    def do(self, index = 0):
        op = self.pos.next[index]
        self.pos = op

        self.commit()

    def do_sequence(self):
        for n in self.pos.next:
            if not n.seq is None:
                seq = n.seq
                op = n
                break
        else:
            raise Exception("No sequence was defined")

        while True:
            for n in op.next:
                if n.seq == seq:
                    op = n
                    break
            else:
                break

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

    def get_branch(self):
        backlog = list(InitialOperationBackwardIterator(self.pos))
        return list(reversed(backlog))

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

                self.__notify_changed(p)


