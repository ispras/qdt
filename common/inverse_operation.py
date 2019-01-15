__all__ = [
    "InverseOperation"
      , "InitialOperation"
  , "UnimplementedInverseOperation"
  , "InitialOperationCall"
  , "History"
  , "Sequence"
  , "HistoryTracker"
]

from six import (
    integer_types
)
from six.moves import (
    zip
)
from .ml import (
    mlget as _
)
from .notifier import (
    notifier
)

class UnimplementedInverseOperation(NotImplementedError):
    pass

simple_eq_types = (
    bool,
    str,
    float
) + integer_types

def set_touches_entry(X, e):
    if isinstance(e, tuple):
        for x in X:
            if isinstance(x, tuple):
                for ee, xx in zip(e, x):
                    if ee != xx:
                        break
                else:
                    return True
            elif isinstance(x, simple_eq_types):
                if e[0] == x:
                    return True
            else:
                raise ValueError("Unsupported type of entry: " + str(type(x)))
    elif isinstance(e, simple_eq_types):
        for x in X:
            if isinstance(x, tuple):
                if e == x[0]:
                    return True
            elif isinstance(x, simple_eq_types):
                if e == x:
                    return True
            else:
                raise ValueError("Unsupported type of entry: " + str(type(x)))
    else:
        raise ValueError("Unsupported type of entry: " + str(type(e)))
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
    """ Describes a deterministic operation that can be done on a context and
consequently undone resulting in the same context state. An operation should
be as basic as possible. A complex "operation" should be presented by a
`sequence` of basic operations. An operation must only contain information
required to perform it. It must be context free and independent. Before an
operation is done it is given a chance to get a backup required for consequent
undoing. The backup must be context independent too. It's possible because of
determinism.
    """

    def __init__(self, previous = None, sequence = None):
        self.prev = previous
        self.next = []
        self.seq = sequence
        self.backed_up = False
        self.done = False

    def backlog(self):
        cur = self
        while cur is not None:
            yield cur
            cur = cur.prev

    def skipped(self):
        for op in self.backlog():
            if not op.done:
                yield op

    def committed(self):
        for op in self.backlog():
            if op.done:
                yield op

    def __backup__(self, context):
        raise UnimplementedInverseOperation()

    def __do__(self, context):
        raise UnimplementedInverseOperation()

    def __undo__(self, context):
        raise UnimplementedInverseOperation()

    def __read_set__(self):
        raise UnimplementedInverseOperation()

    def __write_set__(self):
        raise UnimplementedInverseOperation()

    def writes(self, entry):
        return set_touches_entry(self.__write_set__(), entry)

    def __description__(self, context):
        return _("Reversible operation with unimplemented description \
(class %s).") % type(self).__name__

class InitialOperationCall(TypeError):
    pass

class InitialOperation(InverseOperation):
    def __init__(self):
        InverseOperation.__init__(self)
        self.done = True

    def __backup__(self, _):
        raise InitialOperationCall()

    def __do__(self, _):
        raise InitialOperationCall()

    def __undo__(self, _):
        raise InitialOperationCall()

    def __read_set__(self):
        return []

    def __write_set__(self):
        return []

    def __description__(self, __):
        return _("The beginning of known history.")

class History(object):
    def __init__(self):
        self.root = InitialOperation()
        self.leafs = [self.root]


class Sequence(object):
    """ A dedicated inverse operations sequence that can be applied on demand.
It's like a transaction in a data base management system.
    """

    def __init__(self, ht):
        self.ht = ht
        self._calls, self._staged, self._committed = [], False, False

    def stage(self, *a, **kw):
        self._staged = True
        self._calls.append(("stage", a, kw))

    def commit(self, *a, **kw):
        self._committed = True
        self._calls.append(("commit", a, kw))

    def begin(self):
        "Begins a new sequence and chains it after this one."
        # sequence chaining is supported by the tracker
        return self.ht.begin()

    def __apply__(self):
        if not (self._staged and self._committed):
            # The sequence in incomplete
            return

        ht, calls = self.ht, self._calls

        for method, a, kw in calls:
            getattr(ht, method)(*a, **kw)

@notifier(
    "staged",
    "changed"
)
class HistoryTracker(object):
    def __init__(self, context, history):
        self.ctx = context
        self.history = history
        self.pos = history.leafs[0]
        self.delayed = []

    def begin(self):
        "Begins an operation sequence that will be applied during next commit."
        seq = Sequence(self)
        self.delayed.append(seq)
        return seq

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
            ctx = self.ctx
            for p in queue:
                p.__undo__(ctx)
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
        return self.pos is not self.history.root

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
        return self.pos.next is not None and index < len(self.pos.next)

    def stage(self, op_class, *op_args, **op_kwargs):
        cur = self.pos

        op = op_class(
            *op_args,
            previous = cur,
            **op_kwargs
        )

        if cur in self.history.leafs:
            self.history.leafs.remove(cur)

        self.history.leafs.append(op)
        cur.next.insert(0, op)

        self.pos = op

        self.__notify_staged(op)

        return op

    def get_branch(self):
        return list(reversed(tuple(self.pos.backlog())))

    def commit(self, including = None):
        if including is None:
            including = self.pos

        ctx = self.ctx

        for p in reversed(tuple(including.skipped())):
            # TODO:  check read/write sets before
            # some operations could be skipped if not required
            if not p.backed_up:
                p.__backup__(ctx)
                p.backed_up = True

            p.__do__(ctx)
            p.done = True

            self.__notify_changed(p)

        while self.delayed:
            delayed = list(self.delayed)
            del self.delayed[:]
            for seq in delayed:
                seq.__apply__()

