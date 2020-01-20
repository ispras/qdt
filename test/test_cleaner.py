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


class CleanerTest(TestCase):

    def test_regular(self):
        "Normal program termination"

        def worker(tmpdir, stop_event):
            cleaner = get_cleaner()

            cleaner.rmtree(tmpdir)

            while not stop_event.wait(1.):
                pass

        self._do_test(worker)

    def test_exception(self):
        "Program failure"

        def worker(tmpdir, stop_event):
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

        self._do_test(worker)

    def test_os_exit(self):
        "Explicit program termination"

        def worker(tmpdir, stop_event):
            cleaner = get_cleaner()

            cleaner.rmtree(tmpdir)

            while not stop_event.wait(1.):
                pass

            _exit(0)

        self._do_test(worker)

    def test_cancel(self):
        "Canceling the clean action"

        def worker(tmpdir, stop_event):
            cleaner = get_cleaner()

            task_id = cleaner.rmtree(tmpdir)

            while not stop_event.wait(1.):
                pass

            from shutil import (
                rmtree
            )
            rmtree(tmpdir)
            cleaner.cancel(task_id)

        self._do_test(worker)

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
