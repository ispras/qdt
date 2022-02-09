from unittest import (
    TestCase,
    main
)
from common import (
    get_cleaner
)
from multiprocessing import (
    Process,
    Event
)
from tempfile import (
    mkdtemp
)
from os.path import (
    exists
)
from time import (
    sleep,
    time
)
from os import (
    _exit
)


def regular_worker(tmpdir, stop_event):
    cleaner = get_cleaner()

    cleaner.rmtree(tmpdir)

    while not stop_event.wait(1.):
        pass


def exception_worker(tmpdir, stop_event):
    cleaner = get_cleaner()

    cleaner.rmtree(tmpdir)

    while not stop_event.wait(1.):
        pass

    # Hide consequent exception traceback from user because there is
    # no error actually.
    from os import (
        devnull
    )
    import sys
    sys.stderr = open(devnull, "wb")

    raise Exception


def os_exit_worker(tmpdir, stop_event):
    cleaner = get_cleaner()

    cleaner.rmtree(tmpdir)

    while not stop_event.wait(1.):
        pass

    _exit(0)


def cancel_worker(tmpdir, stop_event):
    cleaner = get_cleaner()

    task_id = cleaner.rmtree(tmpdir)

    while not stop_event.wait(1.):
        pass

    from shutil import (
        rmtree
    )
    rmtree(tmpdir)
    cleaner.cancel(task_id)


class CleanerTest(TestCase):

    def test_regular(self):
        "Normal program termination"

        self._do_test(regular_worker)

    def test_exception(self):
        "Program failure"

        self._do_test(exception_worker)

    def test_os_exit(self):
        "Explicit program termination"

        self._do_test(os_exit_worker)

    def test_cancel(self):
        "Canceling the clean action"

        self._do_test(cancel_worker)

    def _do_test(self, worker):
        tmpdir = mkdtemp()
        stop_event = Event()

        watched = Process(target = worker, args = (tmpdir, stop_event))
        watched.start()

        stop_event.set()
        watched.join()

        t0 = time()
        while exists(tmpdir):
            sleep(0.1)
            self.assertTrue(time() - t0 < 5.,
                "Test directory " + tmpdir + " still exists"
            )


if __name__ == "__main__":
    main()
