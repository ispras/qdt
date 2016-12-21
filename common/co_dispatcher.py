class CoTask(object):
    def __init__(self, generator):
        self.generator = generator

    def on_activated(self):
        # do nothing by default
        pass

    def on_finished(self):
        # do nothing by default
        pass

class CoDispatcher(object):
    """
    The dispatcher for coroutine task.
    The task is assumed to be a generator following the protocol below.

    - Generator yields between 'small' pieces of work. A piece should be small
enough the user will not noticed lags. 
    - Generator yields True if it has a work to do now.
    - Generator yields False if it has not a work to do. For instance, if the
generator waits for something.
    - Generator raise StopIteration when its work is finished. Finished task
will never be given control.

    max_task:
        -1 = unlimited
        0 = do not activate new tasks
        N = limit number of active tasks
    """
    def __init__(self, max_tasks = -1):
        self.tasks = []
        self.active_tasks = []
        self.finished_tasks = []
        self.max_tasks = max_tasks
        self.gen2task = {}

    # poll returns True if at least one task is ready to proceed immediately.
    def poll(self):
        # finished tasks
        to_remove = []

        ready = False

        for task in self.active_tasks:
            try:
                ret = task.generator.next()
            except StopIteration:
                to_remove.append(task)
            else:
                ready = ret or ready

        for task in to_remove:
            # print 'Task %s finished' % str(task)
            self.active_tasks.remove(task)
            self.finished_tasks.append(task)
            task.on_finished()

        return ready

    def remove(self, task):
        if not isinstance(task, CoTask):
            task = self.gen2task[task]

        if task in self.finished_tasks:
            self.finished_tasks.remove(task)
        elif task in self.tasks:
            self.tasks.remove(task)
        else:
            self.active_tasks.remove(task)

        del self.gen2task[task.generator]
        # print 'Task %s was removed' % str(task)

    def enqueue(self, task):
        # just generator can define a task
        if not isinstance(task, CoTask):
            task = CoTask(task)

        self.gen2task[task.generator] = task

        self.tasks.append(task)
        # print 'Task %s was enqueued' % str(task)

    def pull(self):
        if not self.tasks:
            return False

        added = False
        if self.max_tasks < 0:
            added = bool(self.tasks)
            if added:
                while self.tasks:
                    task = self.tasks.pop(0)
                    self.active_tasks.append(task)
                    task.on_activated()
        else:
            rest = self.max_tasks - len(self.active_tasks)
            while rest > 0 and self.tasks:
                rest = rest - 1
                task = self.tasks.pop(0)
                # print 'Activating task %s' % str(task)
                self.active_tasks.append(task)
                task.on_activated()
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
