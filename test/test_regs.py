from unittest import (
    TestCase,
    main
)
from qdt import (
    GUIProject,
    SysBusDeviceDescription,
    Register
)
from common import (
    same
)


def gen_proj():
    return GUIProject(
        descriptions = [
            SysBusDeviceDescription("Test MMIO Device", "test",
                mmio_num = 1,
                mmio = {
                    0 : [
                        Register(1, name = "REG", reset = "0xDEADBEEF")
                    ]
                }
            )
        ]
    )


class InvOpTest(TestCase):

    def test_equality(self):
        self.assertTrue(same(gen_proj(), gen_proj()))


if __name__ == "__main__":
    main()
