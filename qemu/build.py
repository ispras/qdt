__all__ = [
    "register_in_build_system"
  , "register_src_in_build_system"
]

from common import (
    add_line_to_file,
)
from .makefile_patching import (
    patch_makefile,
)
from .version import (
    get_vp,
)

from codecs import (
    open,
)
from collections import (
    defaultdict,
)
from os.path import (
    isfile,
    join,
    split,
    splitext,
)
from re import (
    compile,
)


re_meson_ss_add = compile(b"(\w+)\s*[.]\s*add\s*[(]")
re_meson_ss_new = compile(b"(\w+)\s*=\s*\w+\s*[.]\s*source_set\s*[(]")

# TODO: Selection of configuration flag and accumulator variable
# name is Qemu version specific. Version API must be used there.

obj_var_names = defaultdict(lambda : "obj")
obj_var_names["disas"] = "common-obj"
obj_var_names[join("hw", "pci")] = "common-obj"
obj_var_names["hw"] = "devices-dirs"

config_flags = defaultdict(lambda: "")
config_flags[join("hw", "pci")] = "CONFIG_PCI"
config_flags["hw"] = "CONFIG_SOFTMMU"

# Note that different subdirectories and modules could be registered in "hw"
# using other settings. But as this tool generates devices only. So, the
# settings is chosen this way.


def register_in_build_system(src_root, folder, known_targets):
    tail, head = split(folder)

    if tail:
        # Provide Makefiles in ancestors.
        register_in_build_system(src_root, tail, known_targets)

    # Register the folder in its parent.
    # Note that folders whose names match Qemu target CPU architecture
    # are implicitly included without an entry in "hw/Makefile.objs".
    parent_dir = split(tail)[1]

    if parent_dir == "hw" and known_targets and head in known_targets:
        return

    # Generally, should not register any directory in root directory
    # because it's likely already registered.
    if not parent_dir:
        return

    build_system = get_vp("build system")

    if build_system == "Makefile":
        parent_Makefile_obj = join(src_root, tail, "Makefile.objs")

        # Add empty Makefile.objs if no one exists.
        if not isfile(parent_Makefile_obj):
            open(parent_Makefile_obj, "w").close()

        patch_makefile(parent_Makefile_obj, head + "/",
            obj_var_names[parent_dir], config_flags[parent_dir]
        )
    elif build_system == "meson":
        parent_meson_build = join(src_root, tail, "meson.build")

        # Add empty meson.build if no one exists.
        if not isfile(parent_meson_build):
            open(parent_meson_build, "w").close()

        add_line_to_file(parent_meson_build, "subdir('%s')" % head)
    else:
        print("Folder (" + folder + ") registration in build system '"
            + build_system + "' is not implemented"
        )


def register_src_in_build_system(src_root, sname, directory):
    build_system = get_vp("build system")

    if build_system == "Makefile":
        register_src_in_Makefile(src_root, sname, directory)
    elif build_system == "meson":
        register_src_in_meson(src_root, sname, directory)
    else:
        print("File (" + sname + ") registration in build system '"
            + build_system + "' is not implemented"
        )


def register_src_in_Makefile(src_root, sname, directory):
    sbase, __ = splitext(sname)
    object_name = sbase + ".o"

    Makefile_objs_class_path = join(src_root, directory, "Makefile.objs")

    # If it's a new `hw` subfolder, it has no `Makefile.objs`.
    if not isfile(Makefile_objs_class_path):
        open(Makefile_objs_class_path, "wb").close()

    patch_makefile(Makefile_objs_class_path, object_name,
        obj_var_names[directory], config_flags[directory]
    )


def register_src_in_meson(src_root, sname, directory):
    meson_build = join(src_root, directory, "meson.build")

    source_set = "softmmu_ss"

    if isfile(meson_build):
        # Figure out which source set is most "popular" in this file.
        with open(meson_build, "rb") as f:
            meson_build_data = f.read()
        meson_build_lines = meson_build_data.splitlines()
        used_source_sets = defaultdict(int)
        for l in meson_build_lines:
            mi = re_meson_ss_new.search(l) or re_meson_ss_add.search(l)
            if mi:
                used_source_sets[mi.group(1)] += 1

        if used_source_sets:
            source_set = sorted(
                tuple((-c, s) for (s, c) in used_source_sets.items())
            )[0][1].decode()
    else:
        # If it's a new `hw` subfolder, it has no `meson.build`.
        open(meson_build, "wb").close()

    flag = config_flags[directory]
    if flag:
        line = "%s.add(when: '%s', if_true: files('%s'))" % (
            source_set, flag, sname
        )
    else:
        line = "%s.add(files('%s'))" % (source_set, sname)

    add_line_to_file(meson_build, line)
