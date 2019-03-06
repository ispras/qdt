from unittest import (
    TestCase,
    main
)
from common import (
    SignalDispatcherTask,
    CoDispatcher
)


class CoSignalTest(TestCase):

    def setUp(self):
        self._co_disp = d = CoDispatcher()
        sig_disp = SignalDispatcherTask()
        d.enqueue(sig_disp)
        self._sig = sig_disp.new_signal()

    def test_sig(self):
        self._delivered = None

        def watcher(val):
            self._delivered = val

        self._sig.watch(watcher)
        self._sig.emit("test")

        # the signal is expected to be delivered in two iterations
        limit = 3

        while self._delivered is None and limit:
            self._co_disp.iteration()
            limit -= 1

        self.assertGreater(limit, 0, "Signal has not been delivered")
        self.assertEqual(self._delivered, "test",
            "Delivered '%s' instead of 'test'" % self._delivered
        )

    def test_emits(self):
        self._delivered = 0

        def watcher(a = 1):
            self._delivered |= a

        self._sig.watch(watcher)

        self._sig.emit()
        self._sig.emit(2)
        self._sig.emit(a = 4)

        # all signals is expected to be delivered in four iterations
        limit = 5

        while self._delivered < 7 and limit:
            self._co_disp.iteration()
            limit -= 1

        self.assertGreater(limit, 0, "Signal has not been delivered")
        self.assertEqual(self._delivered, 7,
            "Delivered '%s' instead of '7'" % self._delivered
        )


if __name__ == "__main__":
    main()
