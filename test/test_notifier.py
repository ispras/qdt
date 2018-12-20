from unittest import (
    main,
    TestCase
)
from common import (
    notifier
)


@notifier("e1", "e2")
class Notifier1(object): pass


@notifier("e3")
class Notifier2(Notifier1): pass


class TestNotifier(TestCase):

    def test_event_list(self):
        n1 = Notifier1()

        self.assertEqual(n1.events, ("e1", "e2"))

        n2 = Notifier2()

        self.assertEqual(n2.events, ("e1", "e2", "e3"))


if __name__ == "__main__":
    main()
