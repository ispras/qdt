__all__ = [
# RuntimeError
    "FailedCallee"
  , "CancelledCallee"
# object
  , "CoTask"
  , "CoDispatcher"
# function
  , "callco"
]

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

    def on_activated(self):
        # do nothing by default
        pass

    def on_finished(self):
        # do nothing by default
        pass

    def on_failed(self):
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
        self.finished_tasks = set()
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
                    t0 = time()

                    ret = next(generator)
                else:
                    task._to_raise = None

                    t0 = time()

                    ret = generator.throw(type(to_raise), to_raise)
            except StopIteration:
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

                finished.append(task)
            except Exception as e:
                t1 = time()

                traceback = sys.exc_info()[2]
                lineno = traceback.tb_next.tb_frame.f_lineno

                task.traceback = traceback
                self.__failed__(task, e)
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
            if ti > 0.05:
                sys.stderr.write("Task %s consumed %f sec during iteration "
                    # file:line is the line reference format supported by
                    # Eclipse IDE Console.
                    "between lines %s:%u and %u\n" % (generator.__name__, ti,
                        generator.gi_code.co_filename, task.lineno,
                        lineno
                    )
                )

            task.lineno = lineno

        for task in finished:
            self.__finish__(task)

            try:
                callers = self.callees[task]
            except KeyError:
                continue

            del self.callees[task]
            # All callers of finished task may continue execution.
            for caller in callers:
                del self.callers[caller]
                self.tasks.insert(0, caller)

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
                        self.__activate__(callee)
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

        elif task in self.finished_tasks:
            self.finished_tasks.remove(task)
        elif task in self.tasks:
            self.tasks.remove(task)
        elif task in self.active_tasks:
            self.active_tasks.remove(task)
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

    def __failed__(self, task, exception):
        task.exception = exception
        if task in self.active_tasks:
            self.active_tasks.remove(task)
        self.failed_tasks.add(task)
        task.on_failed()

        try:
            callers = self.callees.pop(task)
        except KeyError:
            self.__root_task_failed__(task)
        else:
            self.__inject_into_callers(callers, FailedCallee(task))

    def __root_task_failed__(self, task):
        pass

    def __finish__(self, task):
        # print 'Task %s finished' % str(task)
        self.active_tasks.remove(task)
        self.finished_tasks.add(task)
        task.on_finished()

    def __activate__(self, task):
        # print 'Activating task %s' % str(task)
        self.active_tasks.append(task)
        task.on_activated()

    def pull(self):
        if not self.tasks:
            return False

        added = False
        if self.max_tasks < 0:
            added = bool(self.tasks)
            if added:
                while self.tasks:
                    task = self.tasks.pop(0)
                    self.__activate__(task)
        else:
            rest = self.max_tasks - len(self.active_tasks)
            while rest > 0 and self.tasks:
                rest = rest - 1
                task = self.tasks.pop(0)
                self.__activate__(task)
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

# Call coroutine maintaining coroutine calling stack.
def callco(co):
    stack = []
    while True:
        try:
            ret = next(co)
        except StopIteration:
            try:
                co = stack.pop()
            except IndexError:
                break
        else:
            if isinstance(ret, GeneratorType):
                stack.append(co)
                co = ret
