__all__ = [
      "Attribute"
    , "StateField"
    , "Register"
    , "RegisterGroup"
    , "RegisterRange"
    , "TargetCPU"
]

from qemu import (
    QOMStateField,
    QOMCPU,
)
from source import (
    Type,
    Variable,
    Initializer,
    Function,
    Pointer,
    Header
)
from numbers import (
    Integral
)

class Attribute(object):
    def __init__(self, name, val):
        self.name = name
        self.val = val

class StateField(QOMStateField):
    def __init__(self, type, name, num = None, save = True):
        super(StateField, self).__init__(type, name, num, save)

# size is reg length in bits
class Register(object):
    def __init__(self, name, size):
        self.name = name
        self.size = size

# this exists for mote convenient handling of
# different CPUState register arrays (dregs, qregs, ...) -
# one group is one such array
class RegisterGroup(object):
    def __init__(self, name, size = 0, regs = []):
        self.name = name
        self.size = size
        self.regs = list(regs)
        if len(regs) > 0:
            assert len(set([reg.size for reg in regs])) == 1
            self.size = regs[0].size

    def add_register(self, reg):
        self.regs.append(reg)
        if self.size > 0:
            assert self.size == reg.size
        else:
            self.size = reg.size

    def add_registers(self, regs):
        for r in regs:
            self.add_register(r)

    def __len__(self):
        return len(self.regs)


class RegisterRange(object):
    def __init__(self,
                 name_start,
                 size,
                 name_end = '',
                 start = 0,
                 end = 1,
                 step = 1
        ):
        self.regs = []
        assert(type(start) == type(end))
        if isinstance(start, Integral):
            func = str
        elif isinstance(start, str) and len(start) == 1:
            func = chr
            start = ord(start[0])
        else:
            raise Exception('Error creating register range: only integer or'
                            'one char ranges are allowed')
        for i in range(start, end, step):
            self.regs.append(Register(name_start + func(i) + name_end, size))


class TargetCPU(object):
    def __init__(self, name, *args):
        self.name = name
        self.qom_cpu = QOMCPU(name)

        self.attrs = {}
        self.fields = []
        self.reg_groups = []
        self.regs = []

        for arg in args:
            if isinstance(arg, Attribute):
                self.attrs.update({arg.name: arg.val})
            elif isinstance(arg, StateField):
                self.fields.append(arg)
            elif isinstance(arg, Register):
                self.regs.append(arg)
                if arg.size <= 32:
                    size = 32
                elif arg.size <= 64:
                    size = 64
                else:
                    raise Exception('Wrong register size: {}'.format(arg.name))
                self.fields.append(
                    StateField(
                        'uint' + str(size) + '_t',
                        arg.name,
                        save = True
                    )
                )
            elif isinstance(arg, RegisterGroup):
                self.reg_groups.append(arg)
                if arg.size <= 32:
                    size = 32
                elif arg.size <= 64:
                    size = 64
                else:
                    raise Exception('Wrong registers size: {}'.format(arg.name))
                self.fields.append(
                    StateField(
                        'uint' + str(size) + '_t',
                        arg.name,
                        num = len(arg.regs),
                        save = True
                    )
                )
            else:
                raise Exception(
                    'Wrong %s CPU field or attribute or register!' % self.name
                )

        self.qom_cpu.add_state_fields(self.fields)

    def get_cpu_name(self):
        return self.name.upper() + 'CPU'

    def get_cpustate_name(self):
        return 'CPU' + self.name.upper() + 'State'

    def gen_state(self):
        return self.qom_cpu.gen_state()

    def gen_qom_model(self, gen_files, generator):
        cpu_c = gen_files['cpu.c']
        helper_c = gen_files['helper.c']
        transl_c = gen_files['translate.c']
        gen_transl = gen_files['translate.inc.c']

        reset = self.qom_cpu.gen_reset()
        disas_set_info = self.qom_cpu.gen_disas_set_info(
            used_types = [Type.lookup('print_insn_' + self.name.lower())]
        )
        generator.gen_disas_set_info(disas_set_info)
        set_pc = self.qom_cpu.gen_set_pc()
        generator.gen_cpu_set_pc(set_pc)

        class_by_name = self.qom_cpu.gen_class_by_name([
            Type.lookup('TYPE_' + self.qom_cpu.arch_name.upper() + '_CPU')
        ])
        generator.gen_class_by_name(class_by_name)

        do_interrupt = self.qom_cpu.gen_do_interrupt()

        gdb_read_register = self.qom_cpu.gdb_read_register(
            used_types = [
                Type.lookup('gdb_get_reg8')
            ]
        )
        generator.gen_gdb_rw_register(
            gdb_read_register,
            "TODO: implement gdb_read_register"
        )

        gdb_write_register = self.qom_cpu.gdb_write_register(
            used_types = [
                Type.lookup('lduw_p')
            ]
        )
        generator.gen_gdb_rw_register(
            gdb_write_register,
            "TODO: implement gdb_write_register"
        )

        phys_page_debug = self.qom_cpu.gen_phys_page_debug()
        generator.gen_get_phys_page_debug(phys_page_debug)

        dump_state = self.qom_cpu.gen_dump_state()
        generator.gen_cpu_dump_state(dump_state, self)

        cpu_env = Variable(
            'cpu_env',
            Type.lookup('TCGv_env'),
            static = True
        )
        transl_c.add_global_variable(cpu_env)
        Header.lookup("exec/gen-icount.h").add_reference(cpu_env)
        reg_vars = []
        for reg_gr in self.reg_groups:
            var = Variable('cpu_' + reg_gr.name,
                Type.lookup('TCGv'),
                array_size = len(reg_gr)
            )
            reg_vars.append(var)
            transl_c.add_global_variable(var)
            var = Variable(
                reg_gr.name,
                Type.lookup('HLTTemp'),
                array_size = len(reg_gr)
            )
            gen_transl.add_global_variable(var)
        for reg in self.regs:
            var = Variable('cpu_' + reg.name,
                           Type.lookup('TCGv'))
            reg_vars.append(var)
            transl_c.add_global_variable(var)
            var = Variable(reg.name,
                           Type.lookup('HLTTemp'))
            gen_transl.add_global_variable(var)

        tcg_init = self.qom_cpu.gen_translate_init()

        realizefn = self.qom_cpu.gen_realize_fn(
            used_types = [
                Type.lookup(self.qom_cpu.arch_name.upper() +
                            '_CPU_CLASS'),
                Type.lookup('qemu_init_vcpu'),
                reset
            ]
        )
        initfn = self.qom_cpu.gen_instance_init_fn(
            used_types = [
                Type.lookup('cpu_exec_init'),
                Type.lookup('tcg_enabled'),
                tcg_init
            ]
        )

        tcg_init_body = tcg_init.gen_body(used_globals = reg_vars + [cpu_env])
        generator.gen_tcg_init(tcg_init_body, reg_vars, cpu_env)

        has_work = self.qom_cpu.gen_has_work()

        cpu_h = gen_files['cpu.h']
        vmstate = Variable(
                'vmstate_' + self.qom_cpu.arch_name + '_cpu',
                Type.lookup('VMStateDescription'),
                const = True
        )
        cpu_h.add_global_variable(vmstate)
        cpu_h.add_type(dump_state)
        cpu_h.add_type(phys_page_debug)
        cpu_h.add_type(do_interrupt)
        cpu_h.add_type(tcg_init)

        cpu_c.add_type(gdb_read_register)
        cpu_c.add_type(gdb_write_register)
        cpu_c.add_type(reset)
        cpu_c.add_type(disas_set_info)
        cpu_c.add_type(set_pc)
        cpu_c.add_type(class_by_name)

        generator.gen_cpu_realizefn(realizefn)
        cpu_c.add_type(realizefn)

        generator.gen_cpu_initfn(initfn)
        cpu_c.add_type(initfn)

        generator.gen_cpu_has_work(has_work)
        cpu_c.add_type(has_work)

        helper_c.add_type(phys_page_debug.gen_body())
        helper_c.add_type(do_interrupt.gen_body())

        raise_exception = self.qom_cpu.raise_exception(
            used_types = [Type.lookup('HELPER_PROTO_H')]
        )
        generator.gen_raise_exception(raise_exception)
        helper_c.add_type(raise_exception)

        helper_debug = self.qom_cpu.helper_debug(
            used_types = [raise_exception]
        )
        generator.gen_helper_debug(helper_debug)
        helper_c.add_type(helper_debug)

        helper_illegal = self.qom_cpu.helper_illegal(
            used_types = [raise_exception]
        )
        generator.gen_helper_illegal(helper_illegal)
        helper_c.add_type(helper_illegal)

        transl_c.add_type(dump_state.gen_body())
        transl_c.add_type(tcg_init_body)

        cpu_init = Function(
            'cpu_' + self.qom_cpu.arch_name + '_init',
            ret_type = Pointer(Type.lookup(self.get_cpu_name())),
            args = [
                Type.lookup('const char').gen_var('cpu_model', pointer = True)
            ]
        )
        cpu_h.add_type(cpu_init)
        cpu_init = cpu_init.gen_body()
        generator.gen_cpu_init(cpu_init)
        cpu_c.add_type(cpu_init)

        # TODO: add vmstate and user-only handle_mmu_fault
        class_init = self.qom_cpu.gen_class_init_fn(
            used_types = [
                gdb_read_register,
                gdb_write_register,
                reset,
                has_work,
                disas_set_info,
                set_pc,
                class_by_name,
                do_interrupt,
                phys_page_debug,
                dump_state,
                realizefn
            ]
        )

        num_core_regs = len(self.regs)
        for gr in self.reg_groups:
            num_core_regs += len(gr)

        generator.gen_cpu_class_initfn(class_init, num_core_regs, vmstate)
        cpu_c.add_type(class_init)

        type_info = Type.lookup('TypeInfo').gen_var(
            self.name + '_type_info',
            initializer = Initializer(
"""{{
    .name = {tname},
    .parent = TYPE_CPU,
    .instance_size = sizeof({cpu_name}),
    .instance_init = {initfn},
    .class_size = sizeof({cname}),
    .class_init = {class_init},
}}""".format
                (
                    tname = 'TYPE_' + self.qom_cpu.arch_name.upper() + '_CPU',
                    cpu_name = self.get_cpu_name(),
                    initfn = initfn.name,
                    cname = self.qom_cpu.arch_name.upper() + 'CPUClass',
                    class_init = class_init.name
                ),
                used_types = [
                     class_init,
                     initfn
                ]
            )
        )
        cpu_c.add_global_variable(type_info)
        type_init = Function(self.name + '_cpu_register_types', static = True,
                             used_globals = [type_info])
        generator.gen_cpu_register(type_init, type_info)
        cpu_c.add_type(type_init)

        type_init_var = Type.lookup("type_init").gen_var()
        type_init_usage_init = Initializer(
            code = {
                "function":  type_init.name
            },
            used_types = [type_init]
        )
        cpu_c.add_usage(
            type_init_var.gen_usage(type_init_usage_init)
        )

    def get_attribute_val(self, name):
        try:
            res = self.attrs[name]
        except KeyError:
            print('Target CPU attribute with name %s not found' % name)
            res = None
        return res
