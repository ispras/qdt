from unittest import (
    TestCase,
    main
)
from qemu import (
    QemuTypeName
)


def names(base):
    qtn = QemuTypeName(base)

    return (
        qtn.for_id_name,
        qtn.for_header_name,
        qtn.for_struct_name,
        qtn.type_macro
    )


class TestQTN(TestCase):

    def test_empty(self):
        QemuTypeName("")

    def test_plus(self):
        self.assertEqual(names("Device+"), (
            "device",
            "device",
            "Device",
            "TYPE_DEVICE"
        ))

    def test_space(self):
        self.assertEqual(names("I/O Device"), (
            "io_device",
            "io_device",
            "IODevice",
            "TYPE_IO_DEVICE"
        ))

    def test_junked_name(self):
        self.assertEqual(names("Device V-2+!@#$%.Ex"), (
            "device_v_2_ex",
            "device_v_2_ex",
            "DeviceV2Ex",
            "TYPE_DEVICE_V_2_EX"
        ))


if __name__ == "__main__":
    main()
