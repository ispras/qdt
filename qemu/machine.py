from qom import \
    QOMType

from source import \
    Source, \
    Type, \
    Initializer, \
    Function

import os.path

class MachineType(QOMType):
    def __init__(self,
                 name,
                 directory):
        super(MachineType, self).__init__(name)

        self.name = name

        source_path = \
            os.path.join("hw", directory, self.qtn.for_header_name + ".c")

        self.source = Source(source_path)

        # machine initialization function
        self.instance_init = Function(
            name = "init_%s" % self.qtn.for_id_name,
            static = True,
            args = [
                Type.lookup("MachineState").gen_var("machine", pointer = True)
                ],
            body = ""
            )
        self.source.add_type(self.instance_init)

        # machine class definition function
        self.class_init = Function(
            name = "machine_%s_class_init" % self.qtn.for_id_name,
            static = True,
            ret_type = Type.lookup("void"),
            args = [
                Type.lookup("ObjectClass").gen_var("oc", pointer = True),
                Type.lookup("void").gen_var("opaque", pointer = True)
                ],
            body = """\
    MachineClass *mc = MACHINE_CLASS(oc);

    mc->name = \"{type_name}\";
    mc->desc = \"{desc}\";
    mc->init = {instance_init};
""".format(
    type_name = self.qtn.for_id_name,
    desc = self.name,
    instance_init = self.instance_init.name
                ),
            used_types = [
                    Type.lookup("MachineClass"),
                    Type.lookup("MACHINE_CLASS"),
                    self.instance_init
                ]
            )
        self.source.add_type(self.class_init)

        # machine type definition structure
        type_machine_macro = Type.lookup("TYPE_MACHINE") 
        type_machine_suf_macro = Type.lookup("TYPE_MACHINE_SUFFIX")

        self.type_info = Type.lookup("TypeInfo").gen_var(
            name = "machine_type_%s" % self.qtn.for_id_name,
            static = True,
            initializer = Initializer(
                code = """{{
    .name = \"{id}\" {suf},
    .parent = {parent},
    .class_init = {class_init}
}}""".format(
                id = self.qtn.for_id_name,
                suf = type_machine_suf_macro.name,
                parent = type_machine_macro.name,
                class_init = self.class_init.name
                ),
            used_types = [
                type_machine_suf_macro,
                type_machine_macro,
                self.class_init
                ]
                )
            )
        self.source.add_global_variable(self.type_info)

        # machine type registration function
        self.type_reg_func = Function(
            name = "machine_init_%s" % self.qtn.for_id_name,
            body = """\
    type_register(&{type_info});
""".format(
    type_info = self.type_info.name
                ),
            static = True,
            used_types = [Type.lookup("type_register")],
            used_globals = [self.type_info]
            )
        self.source.add_type(self.type_reg_func)

        # Main machine registration macro
        machine_init_def = Type.lookup("machine_init").gen_var()
        machine_init_def_args = Initializer(
            code = {"function": self.type_reg_func.name},
            used_types = [self.type_reg_func]
            )
        self.source.add_usage(machine_init_def.gen_usage(machine_init_def_args))

    def generate_source(self):
        return self.source.generate()
