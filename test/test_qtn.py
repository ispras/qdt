from unittest import (
    TestCase,
    main
)
from qemu import (
    QemuTypeName
)


class TestQTN(TestCase):

    def test_empty(self):
        QemuTypeName("")


if __name__ == "__main__":
    main()
