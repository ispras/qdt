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
    History,
    HistoryTracker,
    same
)
from qemu import (
    POp_DelDesc
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

    def test_description_deletion(self):
        ht = HistoryTracker(gen_proj(), History())
        ht.stage(POp_DelDesc, 0)

        p2 = gen_proj()
        self.assertTrue(same(ht.ctx, p2))

        ht.commit()
        ht.undo()

        self.assertTrue(same(ht.ctx, p2))

if __name__ == "__main__":
    main()
