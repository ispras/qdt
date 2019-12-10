from sys import (
    path as PYTHONPATH,
)
from os import (
    environ,
)
from os.path import (
    abspath,
    dirname,
)

PYTHONPATH.insert(0, dirname(dirname(abspath(__file__))))

from qemu import (
    qvd_load_with_cache,
    describable,
    SysBusDeviceType,
    QProject,
)
from source import (
    Function,
    Type,
    Header,
    Call,
)


@describable
class CustomSBDType(SysBusDeviceType):
    """ This is an example of system bus device boilerplate extension with
custom functionality.
    """

    def fill_source(self):
        """ Adds a hook callback in MMIO read handler.
        """

        super().fill_source()

        # Now, code of device's module is generated. It's time to patch it!

        # Assuming, your code uses functions and types from your header.
        custom_h = Header("custom-api.h", is_global = True)

        # If your header is inside Qemu source tree and under Git, then you
        # likely should write above statement as follows:
        #
        # custom_h = Header["custom/custom-api.h"]
        #
        # Because the header is already registered.

        # To use custom functions (and other things) you must declare them.
        # Only name is sufficient because no code will be generated for them.
        custom_h.add_types([
            Function("custom_callback")
        ])

        read_func = self.find_mmio_read_helper(0)

        # We are going to pass second and following argument values of the
        # read helper to the custom callback.
        args2callback = read_func.args[1:]

        # Insert function call statement before 2-nd statement.
        # Note, first statement is likely a variable declaration.
        # This is for prettiness pnly.
        read_func.body.children.insert(1,
            Call("custom_callback", *args2callback)
        )

    def find_mmio_read_helper(self, mmioN):
        # Evaluate name of the read helper.
        # This code came from `super().fill_source()`.
        component = self.get_Ith_mmio_id_component(mmioN)
        name = self.qtn.for_id_name + "_" + component + "_read"

        # Currently all functions (including `static`) are in global name
        # space. And they are "types"... Here it's more generic term then in C.
        return Type[name]


def main():
    p = QProject(
        descriptions = [
            CustomSBDDescription(# This class is defined by `@describable`
                name = "custom_device",
                directory = "misc",
                mmio_num = 1
            ),
        ]
    )

    # We need information about target Qemu source tree.
    # QDT gets it starting from build directory (where `configure` has work).
    qemu_build = environ["QEMU_BUILD_DIR"]

    qemu_version_description = qvd_load_with_cache(qemu_build,
        version = "v4.1.0"
    )
    # First time the loading may take few minutes because Qemu sources
    # are analyzed.
    # Then result is cached in a file to be reused.

    # Apply Qemu's source code environment.
    qemu_version_description.use()

    # And finally, generate the boilerplate
    p.gen_all(qemu_src = qemu_version_description.src_path)


if __name__ == "__main__":
    exit(main() or 0)
