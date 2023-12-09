__all__ = [
    "QProject"
]

from common import (
    add_line_to_file,
    callco,
    co_find_eq,
    makedirs,
    same_sets,
    shadow_open,
)
from .cpu import (
    CPUDescription,
)
from .machine_description import (
    MachineNode,
)
from .makefile_patching import (
    patch_makefile,
)
from source import (
    disable_auto_lock_inclusions,
    enable_auto_lock_inclusions,
    Source,
)
from .version import (
    get_vp,
)
from .version_description import (
    QemuVersionDescription,
)

from codecs import (
    open,
)
from collections import (
    defaultdict,
)
from itertools import (
    count,
)
from os.path import (
    isabs,
    isfile,
    join,
    normpath,
    relpath,
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
obj_var_names["pci"] = "common-obj"
obj_var_names["hw"] = "devices-dirs"

config_flags = defaultdict(lambda: "y")
config_flags["pci"] = "$(CONFIG_PCI)"
config_flags["hw"] = "$(CONFIG_SOFTMMU)"

# Note that different subdirectories and modules could be registered in "hw"
# using other settings. But as this tool generates devices only. So, the
# settings is chosen this way.


class QProject(object):

    def __init__(self,
        descriptions = None
    ):
        self.descriptions = []

        if descriptions is not None:
            for d in descriptions:
                if d.project is not None:
                    raise ValueError("The description '" + d.name
                        +"' is already in another project."
                    )
                else:
                    self.add_description(d)

    def add_description(self, desc):
        desc.project = self
        self.descriptions.append(desc)

    def remove_description(self, desc):
        self.descriptions.remove(desc)
        desc.project = None

    def gen_uniq_desc_name(self):
        for i in count(0):
            cand = "description" + str(i)
            try:
                next(self.find(name = cand))
            except StopIteration:
                return cand

    def find(self, **kw):
        return co_find_eq(self.descriptions, **kw)

    def find1(self, **kw):
        return next(self.find(**kw))

    def gen_all(self, *args, **kw):
        "Backward compatibility wrapper for co_gen_all"
        callco(self.co_gen_all(*args, **kw))

    def co_gen_all(self, qemu_src, **gen_cfg):
        disable_auto_lock_inclusions()
        qvd = QemuVersionDescription.current

        new_targets = set()
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                new_targets.add(desc.directory)

        if new_targets:
            gen_cfg["known_targets"] = (
                gen_cfg.get("known_targets", set()) | new_targets
            )

        # Firstly, generate all CPUs
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                yield desc.gen_type().co_gen(qemu_src, **gen_cfg)

                enable_auto_lock_inclusions()
                # Re-init cache to prevent problems with same named types
                qvd.forget_cache()
                yield qvd.co_init_cache()
                # Replace forgotten dirty cache with new clean one
                qvd.qvc.use()
                disable_auto_lock_inclusions()

        # Secondly, generate all devices
        for desc in self.descriptions:
            if not isinstance(desc, (CPUDescription, MachineNode)):
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        # Lastly, generate machines
        for desc in self.descriptions:
            if isinstance(desc, MachineNode):
                desc.link()
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        enable_auto_lock_inclusions()

    def register_in_build_system(self, folder, known_targets):
        tail, head = split(folder)

        if head == "hw":
            return

        # Provide Makefiles in ancestors.
        self.register_in_build_system(tail, known_targets)

        # Register the folder in its parent.
        # Note that folders whose names match Qemu target CPU architecture
        # are implicitly included without an entry in "hw/Makefile.objs".
        parent_dir = split(tail)[1]

        if parent_dir == "hw" and known_targets and head in known_targets:
            return

        build_system = get_vp("build system")

        if build_system == "Makefile":
            parent_Makefile_obj = join(tail, "Makefile.objs")

            # Add empty Makefile.objs if no one exists.
            if not isfile(parent_Makefile_obj):
                open(parent_Makefile_obj, "w").close()

            patch_makefile(parent_Makefile_obj, head + "/",
                obj_var_names[parent_dir], config_flags[parent_dir]
            )
        elif build_system == "meson":
            parent_meson_build = join(tail, "meson.build")

            # Add empty meson.build if no one exists.
            if not isfile(parent_meson_build):
                open(parent_meson_build, "w").close()

            add_line_to_file(parent_meson_build, "subdir('%s')" % head)
        else:
            print("Folder (" + folder + ") registration in build system '"
                + build_system + "' is not implemented"
            )

    def gen(self, *args, **kw):
        "Backward compatibility wrapper for co_gen"
        callco(self.co_gen(*args, **kw))

    def co_gen(self, desc, src,
        with_chunk_graph = False,
        intermediate_chunk_graphs = False,
        known_targets = None,
        with_debug_comments = False,
        include_paths = tuple(),
        **_
    ):
        build_system = get_vp("build system")

        qom_t = desc.gen_type()

        yield qom_t.co_gen_sources()

        for s in qom_t.sources:
            spath = join(src, s.path)
            sdir, sname = split(spath)

            yield True

            makedirs(sdir, exist_ok = True)

            yield True

            f = s.generate()

            if with_chunk_graph:
                yield True
                f.gen_chunks_gv_file(spath + ".chunks-before-gen.gv")

            yield True

            if intermediate_chunk_graphs:
                graphs_prefix = spath + ".chunks"
            else:
                graphs_prefix = None

            with shadow_open(spath) as stream:
                f.generate(stream,
                    graphs_prefix = graphs_prefix,
                    gen_debug_comments = with_debug_comments,
                    include_paths = include_paths
                )

            if with_chunk_graph:
                yield True
                f.gen_chunks_gv_file(spath + ".chunks-after-gen.gv")

            # Only sources need to be registered in the build system
            if type(s) is not Source:
                continue

            yield
            self.register_in_build_system(sdir, known_targets)

            yield True

            if build_system == "Makefile":
                self.register_src_in_Makefile(src, sname, desc.directory)
            elif build_system == "meson":
                self.register_src_in_meson(src, sname, desc.directory)
            else:
                print("File (" + sname + ") registration in build system '"
                    + build_system + "' is not implemented"
                )

    def register_src_in_Makefile(self, src_root, sname, directory):
        sbase, _ = splitext(sname)
        object_name = sbase + ".o"

        hw_path = join(src_root, "hw")
        class_hw_path = join(hw_path, directory)

        Makefile_objs_class_path = join(class_hw_path, "Makefile.objs")

        # If it's a new `hw` subfolder, it has no `Makefile.objs`.
        if not isfile(Makefile_objs_class_path):
            open(Makefile_objs_class_path, "wb").close()

        patch_makefile(Makefile_objs_class_path, object_name,
            obj_var_names[directory], config_flags[directory]
        )

    def register_src_in_meson(self, src_root, sname, directory):
        hw_path = join(src_root, "hw")
        class_hw_path = join(hw_path, directory)
        meson_build = join(class_hw_path, "meson.build")

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

        line = "%s.add(files('%s'))" % (source_set, sname)

        add_line_to_file(meson_build, line)

    # TODO: add path to `QProject`
    # TODO: def lookup_path

    def replace_relpaths_to_abspaths(self, path):
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                info_path = desc.info_path
                if not info_path:
                    continue
                if not isabs(info_path):
                    desc.info_path = normpath(join(path, info_path))

    def replace_abspaths_to_relpaths(self, path):
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                info_path = desc.info_path
                if not info_path:
                    continue
                if isabs(info_path):
                    desc.info_path = relpath(info_path, start = path)

    def __var_base__(self):
        return "project"

    def __same__(self, o):
        if type(self) is not type(o):
            return False

        # Descriptions order is not significant
        if same_sets(self.descriptions, o.descriptions):
            return True
        return False

    __pygen_deps__ = ("descriptions",)

    def __gen_code__(self, gen):
        gen.gen_code(self)
