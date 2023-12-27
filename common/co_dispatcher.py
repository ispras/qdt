__all__ = [
# RuntimeError
    "FailedCallee"
  , "CancelledCallee"
# BaseException
  , "CoReturn"
# object
  , "CoTask"
  , "CoDispatcher"
      , "CLICoDispatcher"
# function
  , "callco"
]

from time import (
    sleep
)
from types import (
    GeneratorType
)
from time import (
    time
)
from .ml import (
    mlget as _
)
import sys
from traceback import (
    format_exception,
    format_stack,
    print_exception,
)
from .os_wrappers import (
    ee
)


PROFILE_COTASK = ee("QDT_PROFILE_COTASK")


class FailedCallee(RuntimeError):
    def __init__(self, callee):
        super(FailedCallee, self).__init__()
        self.callee = callee

    def __str__(self):
        c = self.callee
        return "Callee '%s' has failed with error %r" % (
            c.generator, c.exception
        )


class CancelledCallee(RuntimeError):
    def __init__(self, callee):
        super(CancelledCallee, self).__init__()
        self.callee = callee

class CoTask(object):
    def __init__(self,
                 generator,
                 enqueued = False,
                 description = _("Coroutine based task without description")
        ):
        self.generator = generator
        self.enqueued = enqueued
        self.description = description

        # Contains the exception if task has failed
        self.exception = None
        # Regular exceptions also have a traceback
        self.traceback = None
        # Line number of last yield.
        # Initially it points to the first line of generator's function.
        self.lineno = generator.gi_code.co_firstlineno
        # Required to preserve the generator frame after it is finished.
        # This information required to get number of last executed line.
        # If a problem will met with this approach then please look at the
        # conversation here:
        # https://stackoverflow.com/questions/49710035/how-to-get-last-line-executed-by-a-generator-in-python
        self.gi_frame = None
        # Exception to be injected into that task at current `yield`.
        self._to_raise = None
        # Value returned by callee. It's returned by `yield`
        self._co_ret = None

    @property
    def traceback_lines(self):
        task = self
        e = task.exception

        if e is None:
            return []

        lines = []

        while isinstance(e, (CancelledCallee, FailedCallee)):
            g = task.generator
            lines.append('In coroutine "%s" (%s):\n' % (
                g.__name__, task.description.get()
            ))
            lines.extend(format_stack(task.gi_frame))

            task = e.callee
            e = task.exception

        g = task.generator
        lines.append('In coroutine "%s" (%s):\n' % (
            g.__name__, task.description.get()
        ))
        lines.extend(format_exception(type(e), e, task.traceback))

        return lines

    def __activated__(self):
        # do nothing by default
        pass

    def __finished__(self):
        # do nothing by default
        pass

    def __failed__(self):
        print_exception(type(self.exception), self.exception, self.traceback)

    def __cancelled__(self):
        # do nothing by default
        pass


class CoDispatcher(object):
    """
    The dispatcher for coroutine task.
    The task is assumed to be a generator following the protocol below.

    - Generator yields between 'small' pieces of work. A piece should be small
enough the user will not noticed lags. 
    - Generator yields True if it has a work to do now.
    - Generator yields other generator (or CoTask) when it cannot continue
until returned one finished. Say, first one _calls_ another.
    - Generator yields False if it has not a work to do right now. For
instance, if the generator waits for something (except other generator).
    - Generator raise StopIteration when its work is finished. Finished task
will never be given control. Note that, StopIteration is raised implicitly
after last statement in the corresponding callable object.

    max_task:
        -1 = unlimited
        0 = do not activate new tasks
        N = limit number of active tasks
    """
    def __init__(self, max_tasks = -1):
        self.tasks = []
        self.active_tasks = []
        # Contains caller list per each callee.
        self.callees = {}
        # Total caller list, I.e. callers = U (callees.values()).
        self.callers = {}
        self.finished_tasks = dict()
        self.failed_tasks = set()
        self.max_tasks = max_tasks
        self.gen2task = {}

    # poll returns True if at least one task is ready to proceed immediately.
    def poll(self):
        finished = []
        calls = []

        ready = False

        for task in self.active_tasks:
            generator = task.generator
            # If the generator is not started yet then just after it yields
            # a reference to its `gi_frame` must be preserved.
            catch_frame = task.gi_frame is None

            to_raise = task._to_raise

            try:
                if to_raise is None:
                    co_ret = task._co_ret

                    if co_ret is None:
                        t0 = time()

                        ret = next(generator)
                    else:
                        task._co_ret = None

                        t0 = time()

                        ret = generator.send(co_ret)
                else:
                    task._to_raise = None

                    t0 = time()

                    ret = generator.throw(type(to_raise), to_raise)
            except (StopIteration, CoReturn) as e:
                t1 = time()

                traceback = sys.exc_info()[2].tb_next
                if traceback is None:
                    # The generator returned without explicit StopIteration
                    # raising. Its `gi_frame` is `None`ed. So use preserved
                    # reference to it.
                    if catch_frame:
                        # XXX: The generator ends in first iteration.
                        # Is there a way to catch its last lineno in this
                        # specific case?
                        lineno = 0
                    else:
                        lineno = task.gi_frame.f_lineno
                else:
                    lineno = traceback.tb_frame.f_lineno

                if isinstance(e, CoReturn):
                    co_ret = e.value
                else:
                    co_ret = None

                finished.append((task, co_ret))
            except Exception as e:
                t1 = time()

                traceback = sys.exc_info()[2]
                lineno = traceback.tb_next.tb_frame.f_lineno

                task.traceback = traceback
                self._failed(task, e)
            else:
                t1 = time()

                if catch_frame:
                    task.gi_frame = generator.gi_frame

                lineno = generator.gi_frame.f_lineno

                if isinstance(ret, (CoTask, GeneratorType)):
                    # remember the call
                    calls.append((task, ret))
                    ready = True
                elif ret:
                    ready = True

            ti = t1 - t0
            if PROFILE_COTASK and ti > 0.05:
                sys.stderr.write("Task %s consumed %f sec during iteration "
                    # file:line is the line reference format supported by
                    # Eclipse IDE Console.
                    "between lines %s:%u and %u\n" % (generator.__name__, ti,
                        generator.gi_code.co_filename, task.lineno,
                        lineno
                    )
                )

            task.lineno = lineno

        for task, co_ret in finished:
            self._finish(task, co_ret)

            try:
                callers = self.callees[task]
            except KeyError:
                continue

            ready = True

            del self.callees[task]
            # All callers of finished task may continue execution.
            for caller in callers:
                del self.callers[caller]
                self.tasks.insert(0, caller)
                caller._co_ret = co_ret

        for caller, callee in calls:
            # Cast callee to CoTask
            if isinstance(callee, GeneratorType):
                try:
                    callee = self.gen2task[callee]
                except KeyError:
                    callee = CoTask(callee)
                    self.gen2task[callee.generator] = callee
                    callee_is_new = True
                else:
                    callee_is_new = False
            else:
                callee_is_new = callee.generator not in self.gen2task
                if callee_is_new:
                    self.gen2task[callee.generator] = callee

            if not callee_is_new and callee in self.finished_tasks:
                # Ignore call of finished task.
                continue

            # A task may call the task which is already called by other task.
            # So, remember all callers of the callee.
            try:
                callers = self.callees[callee]
            except KeyError:
                self.callees[callee] = [caller]
                # First call of the callee.
                # If callee is not a caller too then it should replace its
                # caller. Except the callee is not a new task. Because it
                # is already in task list (should not be scheduled twice).
                if callee not in self.callers:
                    if callee_is_new:
                        self._activate(callee)
            else:
                # The callee is called multiple times. Hence, it is already
                # queued. Just account its new caller.
                callers.append(caller)

            # Caller cannot continue execution until callee finished.
            self.active_tasks.remove(caller)
            # Remember all callers.
            self.callers[caller] = callee

        return ready

    def remove(self, task):
        if not isinstance(task, CoTask):
            task = self.gen2task[task]

        try:
            callers = self.callees.pop(task)
        except KeyError:
            pass
        else:
            self.__inject_into_callers(callers, CancelledCallee(task))

        if task in self.callers:
            callee = self.callers.pop(task)
            callers = self.callees[callee]

            if len(callers) == 1:
                del self.callees[callee]
                # The callee is not required by anything now.
                if not callee.enqueued:
                    # The callee was not enqueued explicitly. Hence, it was
                    # originally called. So, it must be removed as useless.
                    self.remove(callee)
            else:
                callers.remove(task)
            task.__cancelled__()
        elif task in self.finished_tasks:
            self.finished_tasks.pop(task)
        elif task in self.tasks:
            self.tasks.remove(task)
            task.__cancelled__()
        elif task in self.active_tasks:
            self.active_tasks.remove(task)
            task.__cancelled__()
        elif task in self.failed_tasks:
            self.failed_tasks.remove(task)

        del self.gen2task[task.generator]
        # print 'Task %s was removed' % str(task)

    def enqueue(self, task):
        # just generator can define a task
        if not isinstance(task, CoTask):
            try:
                # The task may be added by a call already.
                task = self.gen2task[task]
            except KeyError:
                task = CoTask(task)

        task.enqueued = True
        self.gen2task[task.generator] = task

        self.tasks.append(task)
        # print 'Task %s was enqueued' % str(task)

    def __inject_into_callers(self, tasks, exception):
        for c in list(tasks):
            c._to_raise = exception
            # Wake the caller up giving it a chance to catch the exception
            # around current `yield`.
            del self.callers[c]
            self.tasks.insert(0, c)

    def _failed(self, task, exception):
        task.exception = exception
        if task in self.active_tasks:
            self.active_tasks.remove(task)
        self.failed_tasks.add(task)
        task.__failed__()

        try:
            callers = self.callees.pop(task)
        except KeyError:
            self.__root_task_failed__(task)
        else:
            self.__inject_into_callers(callers, FailedCallee(task))

    def __root_task_failed__(self, task):
        pass

    def _finish(self, task, ret):
        # print 'Task %s finished' % str(task)
        self.active_tasks.remove(task)
        self.finished_tasks[task] = ret
        task.__finished__()

    def _activate(self, task):
        # print 'Activating task %s' % str(task)
        self.active_tasks.append(task)
        task.__activated__()

    def pull(self):
        if not self.tasks:
            return False

        added = False
        if self.max_tasks < 0:
            added = bool(self.tasks)
            if added:
                while self.tasks:
                    task = self.tasks.pop(0)
                    self._activate(task)
        else:
            rest = self.max_tasks - len(self.active_tasks)
            while rest > 0 and self.tasks:
                rest = rest - 1
                task = self.tasks.pop(0)
                self._activate(task)
                added = True

        return added

    def iteration(self):
        if self.pull() or self.active_tasks:
            ready = self.poll()
        else:
            ready = False

        return ready

    def has_work(self):
        return self.tasks or self.active_tasks

    def dispatch_all(self, delay = 0.01):
        has_work, iteration = self.has_work, self.iteration

        if delay is None:
            # No delay mode
            while has_work():
                iteration()
        else:
            while has_work():
                if not iteration():
                    sleep(delay)

    def get_co_ret(self, co):
        if not isinstance(co, CoTask):
            co = self.gen2task[co]
        return self.finished_tasks[co]


class default: pass


class CLICoDispatcher(CoDispatcher):
    def __root_task_failed__(self, task):
        print("".join(task.traceback_lines))


def callco(co, delay = default):
    """ Call `co`routine. See `CoDispatcher` for coroutine protocol.

:param delay: time to wait if a coroutine `yield`ed `False`.

    """
    disp = CLICoDispatcher()
    disp.enqueue(co)
    if delay is default:
        disp.dispatch_all()
    else:
        disp.dispatch_all(delay = delay)

    for t in disp.failed_tasks:
        if t.generator is co:
            raise t.exception

    return disp.get_co_ret(co)


# TODO: There is no _known_ both Py3 & Py2 compatible way to `return` a
# value from a coroutine without specific exception class.
# See: misc/co_return.py

# Note, `CoReturn` is not an _exception_ by meaning. It's a technique to
# return a value from a generator.
# So, it is derived from `BaseException`.
class CoReturn(BaseException):
    """ Use `CoReturn(value)` to return the value from callee. The caller's
`yield` will return the value.
    """

    @property
    def value(self):
        return self.args[0]
