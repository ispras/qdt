from os import \
    makedirs, \
    remove

from os.path import \
    split, \
    join, \
    basename, \
    splitext, \
    isdir, \
    isfile

from itertools import \
    count

from .machine_description import \
    MachineNode

from common import \
    callco, \
    co_find_eq

from .makefile_patching import \
    patch_makefile

from codecs import \
    open

from collections import \
    defaultdict

""" TODO: Selection of configuration flag and accumulator variable
name is Qemu version specific. Version API must be used there. """

obj_var_names = defaultdict(lambda : "obj")
obj_var_names["pci"] = "common-obj"
obj_var_names["hw"] = "devices-dirs"

config_flags = defaultdict(lambda: "y")
config_flags["pci"] = "$(CONFIG_PCI)"
config_flags["hw"] = "$(CONFIG_SOFTMMU)"

""" Note that different subdirectories and modules could be registered in "hw"
using other settings. But as this tool generates devices only. So, the settings
is chosen this way.
"""

class QProject(object):
    def __init__(self,
        descriptions = None
    ):
        self.descriptions = []

        if not descriptions is None:
            for d in descriptions:
                if d.project is not None:
                    raise Exception("The description '" + d.name + "' is \
already in another project.")
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

    """ Backward compatibility wrapper for co_gen_all """
    def gen_all(self, *args, **kw):
        callco(self.co_gen_all(*args, **kw))

    def co_gen_all(self, qemu_src, **gen_cfg):
        # First, generate all devices, then generate machines
        for desc in self.descriptions:
            if not isinstance(desc, MachineNode):
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        for desc in self.descriptions:
            if isinstance(desc, MachineNode):
                desc.link()
                yield self.co_gen(desc, qemu_src, **gen_cfg)

    def make_src_dirs(self, full_path):
        tail, head = split(full_path)

        parent_Makefile_obj = join(tail, "Makefile.objs")

        if not isdir(full_path):
            # Make parent directories.
            if not isfile(parent_Makefile_obj):
                """ Some times, an existing directory (with Makefile.objs)
                will be reached. Then the recursion stops. """
                self.make_src_dirs(tail)

            # Make required directory.
            makedirs(full_path)

        # Add empty Makefile.objs if no one exists.
        Makefile_obj = join(full_path, "Makefile.objs")
        if not isfile(Makefile_obj):
            # Ensure that the directory is registered in the QEMU build system.
            # There is the assumption that a directory with Makefile is
            # always registered. So, do it only when Makefile is just being
            # created.
            parent_dir = split(tail)[1]
            patch_makefile(parent_Makefile_obj, head + "/",
                obj_var_names[parent_dir], config_flags[parent_dir]
            )

            open(Makefile_obj, "w").close()

    """ Backward compatibility wrapper for co_gen """
    def gen(self, *args, **kw):
        callco(self.co_gen(*args, **kw))

    def co_gen(self, desc, src, with_chunk_graph = False):
        dev_t = desc.gen_type()

        full_source_path = join(src, dev_t.source.path)

        source_directory, source_base_name = split(full_source_path)

        self.make_src_dirs(source_directory)

        yield True

        (source_name, source_ext) = splitext(source_base_name)
        object_base_name = source_name + ".o"

        hw_path = join(src, "hw")
        class_hw_path = join(hw_path, desc.directory)
        Makefile_objs_class_path = join(class_hw_path, 'Makefile.objs')

        patch_makefile(Makefile_objs_class_path, object_base_name,
            obj_var_names[desc.directory], config_flags[desc.directory]
        )

        if "header" in dev_t.__dict__:
            yield True

            include_path = join(src, 'include')
            full_header_path = join(include_path, dev_t.header.path)

            # Create intermediate directories
            header_dir = split(full_header_path)[0]
            if not isdir(header_dir):
                makedirs(header_dir)

            if isfile(full_header_path):
                remove(full_header_path)

            yield True

            header_writer = open(full_header_path,
                mode = "wb",
                encoding = "utf-8"
            )
            header = dev_t.generate_header()

            yield True

            header.generate(header_writer)
            header_writer.close()

            if with_chunk_graph:
                yield True
                header.gen_chunks_gv_file(full_header_path + ".chunks.gv")

        yield True

        if isfile(full_source_path):
            remove(full_source_path)

        yield True

        source_writer = open(full_source_path, mode = "wb", encoding = "utf-8")
        source = dev_t.generate_source()

        yield True

        source.generate(source_writer)
        source_writer.close()

        if with_chunk_graph:
            yield True

            source.gen_chunks_gv_file(full_source_path + ".chunks.gv")
