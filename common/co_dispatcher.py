from types import \
    GeneratorType

from time import \
    time

import sys

class CoTask(object):
    def __init__(self,
                 generator,
                 enqueued = False
        ):
        self.generator = generator
        self.enqueued = enqueued

        # Contains the exception if task has failed
        self.exception = None

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
            try:
                t0 = time()

                ret = next(task.generator)
            except StopIteration:
                t1 = time()

                finished.append(task)
            else:
                t1 = time()

                if isinstance(ret, (CoTask, GeneratorType)):
                    # remember the call
                    calls.append((task, ret))
                    ready = True
                elif ret:
                    ready = True

            ti = t1 - t0
            if ti > 0.05:
                sys.stderr.write("Task %s consumed %f sec during iteration\n"
                    % (task.generator.__name__, ti)
                )

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
            callers = self.callees[task]
        except KeyError:
            pass
        else:
            del self.callees[task]
            # Callers of the task cannot continue and must be removed
            for c in list(callers):
                del self.callers[c]
                self.remove(c)

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
