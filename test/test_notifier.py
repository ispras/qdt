from unittest import (
    TestCase,
    main
)
from common import (
    notifier
)


def _n1_with_var_args():
    @notifier("event1")
    class N1WithVarArgs(object):

        def __init__(self, *a):
            self.a = a

    return N1WithVarArgs


def _n2_with_var_args_and_kw_args():
    @notifier("event2")
    class N2WithVarArgsAndKWArgs(_n1_with_var_args()):

        def __init__(self, *a, **kw):
            super(N2WithVarArgsAndKWArgs, self).__init__(*a)
            self.__dict__.update(kw)

    return N2WithVarArgsAndKWArgs


def _no_init_notifier():

    @notifier("e1", "e2")
    class Notifier1(object): pass


class TestNotifier(TestCase):

    def test_var_args(self):
        _n1_with_var_args()

    def test_var_args_and_kw_args(self):
        _n2_with_var_args_and_kw_args()

    def test_no_init_notifier(self):
        _no_init_notifier()

    def test_event_list(self):
        n2 = _n2_with_var_args_and_kw_args()
        n1 = n2.__base__

        self.assertEqual(n1._events, ("event1",))

        self.assertEqual(n2._events, ("event1", "event2"))

@notifier("e")
class N(object):

    def e(self):
        self.__notify_e()


if __name__ == "__main__":

    print(__file__)

    from time import sleep

    def cb():
        print("cb")
        sleep(1.)

    n = N()
    n.watch("e", cb)
    n.e()
    del n



    main()
