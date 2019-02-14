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


class TestNotifier(TestCase):

    def test_var_args(self):
        _n1_with_var_args()

    def test_var_args_and_kw_args(self):
        _n2_with_var_args_and_kw_args()


if __name__ == "__main__":
    main()
