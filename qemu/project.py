from os import \
    remove

from os.path import \
    join, \
    basename, \
    splitext, \
    isfile

from itertools import \
    count

from .machine_description import \
    MachineNode

from common import \
    co_find_eq

from .makefile_patching import \
    patch_makefile

class QProject(object):
    def __init__(self,
        descriptions = None
    ):
        self.descriptions = []

        if not descriptions is None:
            for d in descriptions:
                if not d.project == None:
                    raise Exception("The description '" + d.name + "' is \
already in another project.")
                else:
                    self.add_description(d)

    def add_description(self, desc):
        if desc:
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

    def gen_all(self, qemu_src):
        # First, generate all devices, then generate machines
        for desc in self.descriptions:
            if not isinstance(desc, MachineNode):
                self.gen(desc, qemu_src)

        for desc in self.descriptions:
            if isinstance(desc, MachineNode):
                self.gen(desc, qemu_src)

    def gen(self, desc, src):
        dev_t = desc.gen_type()

        full_source_path = join(src, dev_t.source.path)

        source_base_name = basename(full_source_path)
        (source_name, source_ext) = splitext(source_base_name)
        object_base_name = source_name + ".o"

        hw_path = join(src, "hw")
        class_hw_path = join(hw_path, desc.directory)
        Makefile_objs_class_path = join(class_hw_path, 'Makefile.objs')

        """ TODO: Selection of configuration flag and accumulator variable
        name is Qemu version specific. Version API must be used there. """

        obj_var_names = {
            "pci" : "common-obj"
        }
        config_flags = {
            "pci" : "$(CONFIG_PCI)"
        }

        try:
            obj_var_name = obj_var_names[desc.directory]
        except KeyError:
            obj_var_name = "obj"

        try:
            config_flag = config_flags[desc.directory]
        except KeyError:
            config_flag = "y"

        patch_makefile(Makefile_objs_class_path, object_base_name,
            obj_var_name, config_flag
        )

        if isfile(full_source_path):
            remove(full_source_path)
    
        source_writer = open(full_source_path, "wb")
        source = dev_t.generate_source()
        source.generate(source_writer)
        source_writer.close()

        include_path = join(src, 'include')

        if "header" in dev_t.__dict__:
            full_header_path = join(include_path, dev_t.header.path)
            if isfile(full_header_path):
                remove(full_header_path)
    
            header_writer = open(full_header_path, "wb")
            header = dev_t.generate_header()
            header.generate(header_writer)
            header_writer.close()
