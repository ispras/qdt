__all__ = [
    "QProject"
]

from os import (
    makedirs,
    remove
)
from os.path import (
    split,
    join,
    splitext,
    isdir,
    isfile
)
from itertools import (
    count
)
from .machine_description import (
    MachineNode
)
from common import (
    same_sets,
    callco,
    co_find_eq
)
from .makefile_patching import (
    patch_makefile
)
from codecs import (
    open
)
from collections import (
    defaultdict
)
from source import (
    disable_auto_lock_sources,
    enable_auto_lock_sources,
    Header,
    Source
)

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

        if not descriptions is None:
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
        disable_auto_lock_sources()

        # First, generate all devices, then generate machines
        for desc in self.descriptions:
            if not isinstance(desc, MachineNode):
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        for desc in self.descriptions:
            if isinstance(desc, MachineNode):
                desc.link()
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        enable_auto_lock_sources()

    def register_in_build_system(self, folder, known_targets):
        tail, head = split(folder)

        if head == "hw":
            return

        # Provide Makefiles in ancestors
        self.register_in_build_system(tail, known_targets)

        # Register the folder in its parent
        parent_Makefile_obj = join(tail, "Makefile.objs")
        parent_dir = split(tail)[1]

        if parent_dir == "hw" and known_targets and head in known_targets:
            return

        patch_makefile(parent_Makefile_obj, head + "/",
            obj_var_names[parent_dir], config_flags[parent_dir]
        )

        # Add empty Makefile.objs if no one exists.
        Makefile_obj = join(folder, "Makefile.objs")
        if not isfile(Makefile_obj):
            open(Makefile_obj, "w").close()

    def gen(self, *args, **kw):
        "Backward compatibility wrapper for co_gen"
        callco(self.co_gen(*args, **kw))

    def co_gen(self, desc, src,
        with_chunk_graph = False,
        known_targets = None,
        with_debug_comments = False
    ):
        qom_t = desc.gen_type()

        yield qom_t.co_gen_sources()

        for s in qom_t.sources:
            spath = join(src, s.path)
            sdir, sname = split(spath)

            if isfile(spath):
                yield True
                remove(spath)
            elif not isdir(sdir):
                yield True
                makedirs(sdir)

            if type(s) is Source: # Exactly a compile module
                yield
                self.register_in_build_system(sdir, known_targets)

            yield True

            # TODO: current value of inherit_references is dictated by Qemu
            # coding policy. Hence, version API must be used there.
            inherit_references = type(s) is Header

            f = s.generate(inherit_references = inherit_references)

            with open(spath, mode = "wb", encoding = "utf-8") as stream:
                f.generate(stream, gen_debug_comments = with_debug_comments)

            if with_chunk_graph:
                yield True
                f.gen_chunks_gv_file(spath + ".chunks.gv")

            # Only sources need to be registered in the build system
            if type(s) is not Source:
                continue

            yield True

            sbase, _ = splitext(sname)
            object_name = sbase + ".o"

            hw_path = join(src, "hw")
            class_hw_path = join(hw_path, desc.directory)
            Makefile_objs_class_path = join(class_hw_path, "Makefile.objs")

            patch_makefile(Makefile_objs_class_path, object_name,
                obj_var_names[desc.directory], config_flags[desc.directory]
            )

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
