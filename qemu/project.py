import os
from itertools import \
    count
from machine_description import \
    MachineNode
from common import \
    co_find_eq

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
                self.find(name = cand).next()
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

        full_source_path = os.path.join(src, dev_t.source.path)

        source_base_name = os.path.basename(full_source_path)
        (source_name, source_ext) = os.path.splitext(source_base_name)
        object_base_name = source_name + ".o"

        hw_path = os.path.join(src, "hw")
        class_hw_path = os.path.join(hw_path, desc.directory)
        Makefile_objs_class_path = os.path.join(class_hw_path, 'Makefile.objs')

        registered_in_makefile = False
        for line in open(Makefile_objs_class_path, "r").readlines():
            if object_base_name in [s.strip() for s in line.split(" ")]:
                registered_in_makefile = True
                break
    
        if not registered_in_makefile:
            with open(Makefile_objs_class_path, "a") as Makefile_objs:
                Makefile_objs.write(u"obj-y += %s\n" % object_base_name)
    
        if os.path.isfile(full_source_path):
            os.remove(full_source_path)
    
        source_writer = open(full_source_path, "wb")
        source = dev_t.generate_source()
        source.generate(source_writer)
        source_writer.close()

        include_path = os.path.join(src, 'include')

        if "header" in dev_t.__dict__:
            full_header_path = os.path.join(include_path, dev_t.header.path)
            if os.path.isfile(full_header_path):
                os.remove(full_header_path)
    
            header_writer = open(full_header_path, "wb")
            header = dev_t.generate_header()
            header.generate(header_writer)
            header_writer.close()
