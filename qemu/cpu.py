__all__ = [
    "TargetCPU"
  , "gen_registers_range"
]

from os import (
    makedirs
)
from os.path import (
    sep,
    exists,
    join,
    basename,
    splitext
)
from sys import (
    stderr
)
from codecs import (
    open
)
from .qom import (
    QOMStateField,
    QOMCPU,
    CPURegister
)
from source import (
    Header,
    Source,
    Type,
    Variable,
    Initializer,
    Function,
    Structure,
    Pointer,
    Macro,
    Enumeration
)
from numbers import (
    Integral
)
from .version import (
    get_vp
)
from .instruction import (
    BYTE_SIZE,
    parse_endian
)
from re import (
    compile
)
from collections import (
    defaultdict,
    OrderedDict
)
from .makefile_patching import (
    patch_makefile
)
from .target_code_generator import (
    TargetCodeGenerator,
    CPURegisterGroup
)


def gen_registers_range(name_start, size,
        name_end = "",
        start = 0,
        end = 1,
        step = 1
    ):
        assert(type(start) == type(end))
        if isinstance(start, Integral):
            func = str
        elif isinstance(start, str) and len(start) == 1:
            func = chr
            start = ord(start[0])
        else:
            raise ValueError(
"Error creating register range: only integer or one char ranges are allowed"
            )
        return [CPURegister(name_start + func(i) + name_end, size)
            for i in range(start, end, step)
        ]


class InstructionNode(object):

    def __init__(self, opcode = None):
        self.opcode = opcode
        self.opc_dict = {}

        # unparsed yet
        self.instructions = []
        # already parsed one
        self.instruction = None

        self.count = 0
        self.instr_mnemonic = ""

    def dump(self):
        print("\nInsNode: " + str(self) + "[" + str(self.opcode) + "]")
        if self.count > 0:
            print(self.instructions[0].name)
            if self.count > 1:
                stderr.write("Warning: InstructionNode.count > 1 !")
        else:
            for key, node in self.opc_dict.iteritems():
                print("\n" + str(self) + " [" + str(key) + "] -> " + str(node))
                node.dump()


def find_common_opcode_intervals(instructions):
    """ Finds bit intervals occupied by opcodes in all instructions.

    :returns: list of tuples: [(off_1, len_1), ..., (off_k, len_k), ...]
    """

    strs = [ instr.string for instr in instructions ]
    result = []
    cur_len = 0
    off = 0
    for i in range(min([len(string) for string in strs])):
        for x in strs:
            if x[i] not in "01":
                if cur_len > 0:
                    result.append((off, cur_len))
                    cur_len = 0
                break
        else:
            if cur_len == 0:
                off = i
            cur_len += 1
    # process tail
    if cur_len > 0:
        result.append((off, cur_len))
    return result


def build_instruction_tree(instructions,
    cur_node = None,
    depth = 0,
    prev_instructions = [],
    checked_opc = [],
    verbose = False
):
    if instructions == prev_instructions:
        raise Exception("Recursion error")

    orig_opc = find_common_opcode_intervals(instructions)
    for part in orig_opc:
        vals = set()
        for i in instructions:
            vals.add(int(i.get_opcode_part(part)))
        if len(vals) > 1:
            opc = part
            break
    else:
        opc = orig_opc[0]

    # create root
    if cur_node is None:
        cur_node = InstructionNode(opc)
    else:
        cur_node.opcode = opc

    unique = set(instructions)
    cur_node.count = len(unique)
    if len(unique) == 1:
        unchecked_opc = set(orig_opc).difference(set(checked_opc))
        ins = unique.pop()
        for opc in unchecked_opc:
            cur_node.opcode = opc
            key = ins.get_opcode_part(opc)
            ins_node = InstructionNode()
            cur_node.opc_dict[key] = ins_node
            cur_node = ins_node

        cur_node.instruction = ins

        # believe that instructions with identical opcode
        # can't vary in length
        assert(len(set([len(ins) for ins in instructions])))

        cur_node.instr_mnemonic = instructions[0].mnem
        return cur_node

    opcs = [inst.get_opcode_part(opc) for inst in instructions]
    opc_set = set(opcs)
    div_num = len(opc_set)

    conflict = False
    if div_num <= 1:
        if verbose:
            print("Instructions conflict found")
            for instr in instructions:
                instr.dump()
        conflict = True
        for j in instructions:
            offset = 0
            for f in j.fields:
                opcodes_found = 0
                length = f.length
                for i in instructions:
                    opcodes_found += i.has_opcode(offset, length)

                if 0 < opcodes_found < len(instructions):
                    # that means we can divide N instructions
                    # into N different classes
                    # by N-1 opcode cases and default case
                    conflict = False
                    opc = (offset, length)
                    cur_node.opcode = opc
                    if verbose:
                        print("Conflict resolved")
                    break
                offset += length
            if not conflict:
                break
    if conflict:
        if verbose:
            print("FAIL: conflict for ops:")
            for instr in instructions:
                instr.dump(verbose = True)
        raise Exception('Unresolved conflict: "%s" with "%s"' % (
            instructions[0].comment or instructions[0].name,
            instructions[1].comment or instructions[1].name
        ))

    tmp_dict = defaultdict(list)
    for ins in instructions:
        key = ins.get_opcode_part(opc)
        if key is None or len(key) != opc[1]:
            key = "default"
        tmp_dict[key].append(ins)
    new_checked_opc = list(checked_opc)
    new_checked_opc.append(opc)
    for key, instrs in tmp_dict.items():
        cur_node.opc_dict[key] = InstructionNode()
        build_instruction_tree(instrs,
            cur_node = cur_node.opc_dict[key],
            depth = depth + 1,
            prev_instructions = instructions,
            checked_opc = new_checked_opc,
            verbose = verbose
        )

    return cur_node


class TargetCPU(object):

    def __init__(self, name, ins_set,
        endianess = "little",
        qemu_root = None,
        custom_target_name = None,
        registers = None,
        attributes = None
    ):
        self.qom_cpu = QOMCPU(name)

        self.attrs = {} if attributes is None else attributes
        self.raw_args = [] if registers is None else registers
        self.fields = []
        self.reg_groups = []
        self.regs = []

        self.target_name = custom_target_name or self.qom_cpu.arch_name
        self.qemu_root = qemu_root

        self.arch_bigendian = parse_endian(endianess)

        self.name_to_format = ins_set.name_to_format
        self.read_size = ins_set.read_size

        self.need_fit_endian = ins_set.desc_bigendian == self.arch_bigendian

        tmp = []
        for i in ins_set.instruction_list:
            tmp.extend(i.expand(self.read_size * BYTE_SIZE))
        self.instructions = tmp

        lens = [len(instr) for instr in self.instructions]
        min_size = min(lens)
        max_size = max(lens)
        instr_size_is_fixed = min_size == max_size

        print(
"{arch} is a {endianess}-endian {is_fixed} instruction size architecture with "
"{size_info}".format(
    arch = self.target_name.upper(),
    endianess = endianess.lower(),
    is_fixed = "fixed" if instr_size_is_fixed else "variable",
    size_info = ("size = %d" % min_size if instr_size_is_fixed else
        "min_size = %d and max_size = %d" % (min_size, max_size)
    )
)
        )

    def gen_state(self):
        for arg in self.raw_args:
            if isinstance(arg, QOMStateField):
                self.fields.append(arg)
            elif isinstance(arg, CPURegister):
                self.regs.append(arg)
                if arg.size <= 32:
                    size = 32
                elif arg.size <= 64:
                    size = 64
                else:
                    raise ValueError("Wrong register size: " + arg.name)
                self.fields.append(
                    QOMStateField(
                        Type["uint" + str(size) + "_t"],
                        arg.name,
                        save = True
                    )
                )
            elif isinstance(arg, CPURegisterGroup):
                self.reg_groups.append(arg)
                if arg.size <= 32:
                    size = 32
                elif arg.size <= 64:
                    size = 64
                else:
                    raise ValueError("Wrong registers size: " + arg.name)
                self.fields.append(
                    QOMStateField(
                        Type["uint" + str(size) + "_t"],
                        arg.name,
                        num = len(arg.regs),
                        save = True
                    )
                )
            else:
                raise ValueError("Unexpected field of CPU")

        self.qom_cpu.add_state_fields(self.fields)

        return self.qom_cpu.gen_state()

    def gen_qom_model(self, gen_files, generator):
        cpu_c = gen_files["cpu.c"]
        transl_c = gen_files["translate.c"]
        gen_transl = gen_files["translate.inc.c"]

        cpu_class = Type["CPUClass"]

        reset = cpu_class.reset.type.type.use_as_prototype(
            self.qom_cpu.func_name("reset"),
            static = True
        )

        disas_set_info = cpu_class.disas_set_info.type.type.use_as_prototype(
            self.qom_cpu.func_name("disas_set_info"),
            static = True
        )
        generator.gen_disas_set_info(disas_set_info)

        set_pc = cpu_class.set_pc.type.type.use_as_prototype(
            self.qom_cpu.func_name("set_pc"),
            static = True
        )
        generator.gen_cpu_set_pc(set_pc)

        class_by_name = cpu_class.class_by_name.type.type.use_as_prototype(
            self.qom_cpu.func_name("class_by_name"),
            static = True
        )
        generator.gen_class_by_name(class_by_name)

        do_interrupt = cpu_class.do_interrupt.type.type.use_as_prototype(
            self.qom_cpu.func_name("do_interrupt")
        )

        gdb_read_register = (cpu_class.gdb_read_register.type.type.
            use_as_prototype(
                self.qom_cpu.func_name("gdb_read_register"),
                static = True
            )
        )
        generator.gen_gdb_rw_register(
            gdb_read_register,
            "TODO: implement gdb_read_register"
        )

        gdb_write_register = (cpu_class.gdb_write_register.type.type.
            use_as_prototype(
                self.qom_cpu.func_name("gdb_write_register"),
                static = True
            )
        )
        generator.gen_gdb_rw_register(
            gdb_write_register,
            "TODO: implement gdb_write_register"
        )

        phys_page_debug = (cpu_class.get_phys_page_debug.type.type.
            use_as_prototype(self.qom_cpu.func_name("get_phys_page_debug"))
        )

        dump_state = cpu_class.dump_state.type.type.use_as_prototype(
            self.qom_cpu.func_name("dump_state")
        )

        if get_vp("Init cpu_env in arch"):
            cpu_env = Variable(
                "cpu_env",
                Type["TCGv_env"],
                static = True
            )
            transl_c.add_global_variable(cpu_env)
            Header["exec/gen-icount.h"].add_reference(cpu_env)
        else:
            cpu_env = Header["tcg.h"].global_variables["cpu_env"]

        reg_vars = []
        for reg_gr in self.reg_groups:
            reg_var = Variable(
                "cpu_" + reg_gr.name,
                Type["TCGv"],
                array_size = len(reg_gr)
            )
            transl_c.add_global_variable(reg_var)

            reg_name = Type["const char"].gen_var(
                reg_gr.name + "_names",
                pointer = True,
                initializer = Initializer(
                    code = ('{\n    "' +
                        '",\n    "'.join(r.name for r in reg_gr.regs) + '"\n}'
                    )
                ),
                static = True,
                array_size = len(reg_gr)
            )
            transl_c.add_global_variable(reg_name)

            reg_vars.append((reg_gr, reg_var, reg_name))

            var = Variable(
                reg_gr.name,
                Type["HLTTemp"],
                array_size = len(reg_gr)
            )
            gen_transl.add_global_variable(var)
        for reg in self.regs:
            var = Variable("cpu_" + reg.name, Type["TCGv"])
            reg_vars.append((reg, var, None))
            transl_c.add_global_variable(var)
            gen_transl.add_global_variable(Variable(reg.name, Type["HLTTemp"]))

        tcg_init = Function(name = self.qom_cpu.tcg_init_name())

        realizefn = Type["DeviceRealize"].type.use_as_prototype(
            self.qom_cpu.func_name("realizefn"),
            static = True
        )
        generator.gen_cpu_realizefn(realizefn)

        initfn = Type["TypeInfo"].instance_init.type.type.use_as_prototype(
            self.qom_cpu.func_name("initfn"),
            static = True
        )
        generator.gen_cpu_initfn(initfn)

        has_work = cpu_class.has_work.type.type.use_as_prototype(
            self.qom_cpu.func_name("has_work"),
            static = True
        )
        generator.gen_cpu_has_work(has_work)

        cpu_h = gen_files["cpu.h"]
        vmstate = Variable(
            "vmstate_" + self.qom_cpu.qtn.for_id_name,
            Type["VMStateDescription"],
            const = True
        )
        cpu_h.add_global_variable(vmstate)
        cpu_h.add_types([
            dump_state,
            phys_page_debug,
            do_interrupt,
            tcg_init
        ])

        cpu_c.add_types([
            gdb_read_register,
            gdb_write_register,
            reset,
            disas_set_info,
            set_pc,
            class_by_name,
            realizefn,
            initfn,
            has_work
        ])

        phys_page_debug_def = phys_page_debug.gen_definition()
        generator.gen_get_phys_page_debug(phys_page_debug_def)

        raise_exception = self.qom_cpu.raise_exception()
        generator.gen_raise_exception(raise_exception)

        helper_debug = self.qom_cpu.helper_debug()
        generator.gen_helper_debug(helper_debug)

        helper_illegal = self.qom_cpu.helper_illegal()
        generator.gen_helper_illegal(helper_illegal)

        gen_files["helper.c"].add_types([
            phys_page_debug_def,
            do_interrupt.gen_definition(),
            raise_exception,
            helper_debug,
            helper_illegal
        ])

        Header["exec/helper-gen.h"].add_types([
            helper_debug.use_as_prototype("gen_" + helper_debug.name),
            helper_illegal.use_as_prototype("gen_" + helper_illegal.name)
        ])

        dump_state_def = dump_state.gen_definition()
        generator.gen_cpu_dump_state(dump_state_def)

        tcg_init_def = tcg_init.gen_definition()
        generator.gen_tcg_init(tcg_init_def, reg_vars, cpu_env)

        transl_c.add_types([
            dump_state_def,
            tcg_init_def
        ])

        if get_vp("Create cpu_init"):
            cpu_init = Function(
                name = self.qom_cpu.cpu_init_name(),
                ret_type = Pointer(Type[self.qom_cpu.struct_name]),
                args = [
                    Type["const char"].gen_var("cpu_model", pointer = True)
                ]
            )
            cpu_init_def = cpu_init.gen_definition()
            generator.gen_cpu_init(cpu_init_def)

            cpu_h.add_type(cpu_init)
            cpu_c.add_type(cpu_init_def)

        class_init = Type["TypeInfo"].class_init.type.type.use_as_prototype(
            self.qom_cpu.func_name("class_init"),
            static = True
        )

        num_core_regs = len(self.regs)
        for gr in self.reg_groups:
            num_core_regs += len(gr)

        generator.gen_cpu_class_initfn(class_init, num_core_regs, vmstate)
        cpu_c.add_type(class_init)

        type_info = Type["TypeInfo"].gen_var(self.qom_cpu.type_info_name(),
            initializer = Initializer({
                "name": Type[self.qom_cpu.qtn.type_macro],
                "parent": Type["TYPE_CPU"],
                "instance_size": "sizeof(" + self.qom_cpu.struct_name + ")",
                "instance_init": initfn,
                "class_size": ("sizeof(" + self.qom_cpu.struct_class_name() +
                    ")"
                ),
                "class_init": class_init
            })
        )
        cpu_c.add_global_variable(type_info)

        type_init = Function(
            name = self.qom_cpu.func_name("register_types"),
            static = True
        )
        generator.gen_cpu_register(type_init, type_info)
        cpu_c.add_type(type_init)

        type_init_usage_init = Initializer({ "function":  type_init })
        cpu_c.add_type(Type["type_init"].gen_usage(type_init_usage_init))

    def get_attribute_val(self, name):
        try:
            res = self.attrs[name]
        except KeyError:
            print("Target CPU attribute with name " + name + " not found")
            res = None
        return res

    def gen_target_code(self, qemu_src, verbose = False):
        # maybe should correct opc index (e.g. common opcode is in the middle,
        # but some instructions have common parts before

        def create_default_config(src):
            with open(
                join(src, "default-configs",
                    self.target_name + "-softmmu.mak"
                ),
                "w"
            ) as f:
                f.write("# Default configuration for " + self.target_name +
                    "-softmmu"
                )

        def update_configure(src):
            configure_path = join(src, "configure")
            with open(configure_path, "r") as f:
                lines = f.readlines()

            insert_be = not self.arch_bigendian
            insert_target = False
            insert_disas_config = False
            find_target_abi_dir = False
            find_disas_config = False
            for i, line in enumerate(lines):
                if line == 'TARGET_ABI_DIR=""\n':
                    find_target_abi_dir = True
                if find_target_abi_dir and not insert_target:
                    if lines[i] == "  " + self.target_name + ")\n":
                        return
                    if lines[i] == "  *)\n":
                        lines.insert(
                            i,
                            """\
  {tn})
    TARGET_ARCH={tn}
    TARGET_BASE_ARCH={tn}
  ;;
""".format(tn = self.target_name)
                        )
                        insert_target = True

                if line == "disas_config() {\n":
                    find_disas_config = True
                if find_disas_config and not insert_disas_config:
                    if line == "  " + self.target_name + ")\n":
                        return
                    if line == "  esac\n":
                        lines.insert(
                            i,
                            """\
  {tn})
    disas_config "{TN}"
  ;;
""".format(tn = self.target_name, TN = self.target_name.upper())
                        )
                        insert_disas_config = True

                if not insert_be and lines[i] == 'target_bigendian="no"\n':
                    if lines[i + 3].find(self.target_name + '|') != -1:
                        return
                    lines[i + 3] = ("  " + self.target_name + '|' +
                        lines[i + 3].lstrip()
                    )
                    insert_be = True

                if insert_be and insert_target and insert_disas_config:
                    break

            with open(configure_path, "w") as f:
                f.write("".join(lines))

        def update_archinit(src):
            arch_init_header = join(src, "include", "sysemu", "arch_init.h")
            with open(arch_init_header, "r") as f:
                lines = f.readlines()

            offset = -2
            str_qemu_arch = "    QEMU_ARCH_" + self.target_name.upper()
            for i, line in enumerate(lines):
                if line == "    QEMU_ARCH_ALL = -1,\n":
                    offset = -1

                if offset != -2:
                    if str_qemu_arch in line:
                        break
                    elif "QEMU_ARCH_" in line:
                        offset += 1
                    elif line == "};\n":
                        lines.insert(
                            i,
                            str_qemu_arch + " = (1 << " + str(offset) + "),\n"
                        )
                        break

            with open(arch_init_header, "w") as f:
                f.write("".join(lines))

            arch_init_source = join(src, "arch_init.c")
            with open(arch_init_source, "r") as f:
                lines = f.readlines()

            str_target = "TARGET_" + self.target_name.upper()
            for i, line in enumerate(lines):
                if str_target in line:
                    return

                if (    line == "#endif\n"
                    and "#define QEMU_ARCH QEMU_ARCH_" in lines[i - 1]
                ):
                    lines.insert(
                        i,
                        """\
#elif defined({})
#define QEMU_ARCH QEMU_ARCH_{}
""".format(str_target, self.target_name.upper())
                    )
                    break

            with open(arch_init_source, "w") as f:
                f.write("".join(lines))

        def update_bfd(src):
            bfd_header = join(src, "include", "disas", "bfd.h")
            with open(bfd_header, "r") as f:
                lines = f.readlines()

            Header["disas/bfd.h"].add_type(
                Enumeration("bfd_architecture",
                    {
                        # not real value
                        "bfd_arch_" + self.target_name : 0
                    }
                )
            )

            bfd_arch = "  bfd_arch_" + self.target_name + ",\n"
            for i, line in enumerate(lines):
                if line == bfd_arch:
                    break
                elif line == "  bfd_arch_last\n":
                    lines.insert(i, bfd_arch)
                    break

            decl_func = ("int print_insn_" + self.target_name +
                "(bfd_vma, disassemble_info*);\n"
            )

            disas_decl = Function(
                name = "print_insn_" + self.target_name,
                ret_type = Type["int"],
                args = [
                    Type["bfd_vma"].gen_var("addr"),
                    Type["disassemble_info"].gen_var("info", pointer = True)
                ]
            )
            Header["disas/bfd.h"].add_type(disas_decl)

            to_print = False
            for i, line in enumerate(lines):
                if "print_insn_" in line:
                    to_print = True
                    if line == decl_func:
                        break
                elif to_print:
                    lines.insert(
                        i,
                        decl_func
                    )
                    break;

            with open(bfd_header, "w") as f:
                f.write("".join(lines))

        # here mkdir target-$(ARCH_NAME) and gen all necessary files
        def gen_target_files():
            hdr = self.gen_files["cpu.h"]

            exec_c = Source("exec.c")
            exec_c.add_reference(Type["TARGET_PAGE_SIZE"])
            exec_c.add_inclusion(hdr)

            cpu_arch_state = self.gen_state()
            hdr.add_type(cpu_arch_state)

            qtn = self.qom_cpu.qtn

            state_macro = Macro(
                "CPUArchState",
                text = "struct " + cpu_arch_state.name
            )
            hdr.add_type(state_macro)
            Header["tcg.h"].add_reference(state_macro)
            Header["exec/cpu-all.h"].add_reference(state_macro)
            Header["exec/cpu-all.h"].add_reference(Type["TARGET_LONG_SIZE"])

            target_defines = [
                "TARGET_LONG_BITS",
                "TARGET_PAGE_BITS",
                "TARGET_PHYS_ADDR_SPACE_BITS",
                "TARGET_VIRT_ADDR_SPACE_BITS",
                "NB_MMU_MODES"
            ]

            for define_name in target_defines:
                m = Macro(
                    define_name,
                    text = self.get_attribute_val(define_name)
                )

                hdr.add_type(m)
                if define_name in ["TARGET_LONG_BITS", "NB_MMU_MODES"]:
                    Header["exec/cpu-defs.h"].add_reference(m)

            arch_cpu = Structure(self.qom_cpu.struct_name)
            arch_cpu.append_field_t_s("CPUState", "parent_obj")
            arch_cpu.append_field_t_s(cpu_arch_state.name, "env")
            hdr.add_type(arch_cpu)

            if get_vp("CPU_RESOLVING_TYPE"):
                cpu_resolv = Macro(
                    "CPU_RESOLVING_TYPE",
                    text = qtn.type_macro
                )
                hdr.add_type(cpu_resolv)

            if get_vp("Create cpu_init"):
                hdr.add_type(
                    Macro(
                        "cpu_init",
                        args = ["cpu_model"],
                        text = "CPU(%s(cpu_model))" % (
                            self.qom_cpu.cpu_init_name()
                        )
                    )
                )

            hdr.add_type(
                Enumeration(
                    "excp_enum",
                    {
                        "EXCP_ILLEGAL": 1
                    }
                )
            )

            handle_mmu_fault_decl = Function(
                name = self.qom_cpu.func_name("handle_mmu_fault"),
                ret_type = Type["int"],
                args = [
                    Type["CPUState"].gen_var("cs", pointer = True),
                    Type["vaddr"].gen_var("address"),
                    Type["int"].gen_var("rw"),
                    Type["int"].gen_var("mmu_idx")
                ]
            )
            hdr.add_type(handle_mmu_fault_decl)

            m_env_offset = Macro(
                "ENV_OFFSET",
                text = "offsetof(" + arch_cpu.name + ", env)"
            )
            hdr.add_type(m_env_offset)

            env_get_cpu = Function(
                name = self.qom_cpu.env_get_cpu_name(),
                ret_type = Pointer(arch_cpu),
                static = True,
                inline = True,
                args = [cpu_arch_state.gen_var("env", pointer = True)]
            )
            self.g.gen_env_get_cpu(env_get_cpu)
            hdr.add_type(env_get_cpu)

            hdr.add_type(
                Macro(
                    "ENV_GET_CPU",
                    ["e"],
                    "CPU(" + env_get_cpu.name + "(e))"
                )
            )

            cpu_mmu_index = Function(
                name = "cpu_mmu_index",
                ret_type = Type["int"],
                static = True,
                inline = True,
                args = [
                    cpu_arch_state.gen_var("env", pointer = True),
                    Type["bool"].gen_var("ifetch")
                ]
            )
            self.g.gen_cpu_mmu_index(cpu_mmu_index)
            hdr.add_type(cpu_mmu_index)

            get_tb_cpu_state = Function(
                name = "cpu_get_tb_cpu_state",
                static = True,
                inline = True,
                args = [
                    cpu_arch_state.gen_var("env", pointer = True),
                    Type["target_ulong"].gen_var("pc", pointer = True),
                    Type["target_ulong"].gen_var("cs_base", pointer = True),
                    Type["uint32_t"].gen_var("flags", pointer = True)
                ]
            )
            self.g.gen_cpu_get_tb_cpu_state(get_tb_cpu_state)
            hdr.add_type(get_tb_cpu_state)

            hdr.add_reference(Type["MIN"])
            Header["exec/exec-all.h"].add_reference(Type["CPUArchState"])

            type_arch_cpu = Macro(
                qtn.type_macro,
                text = '"'+ qtn.name + '"'
            )
            hdr.add_type(type_arch_cpu)

            cpu_class = Structure(self.qom_cpu.struct_class_name())
            cpu_class.append_field_t_s("CPUClass", "parent_class")
            cpu_class.append_field_t_s("DeviceRealize", "parent_realize")
            cpu_class.append_field(
                Function(
                    args = [Type["CPUState"].gen_var("cpu", pointer = True)]
                ).gen_var("parent_reset")
            )
            cpu_class.append_field_t_s("uint32_t", "vr")
            hdr.add_type(cpu_class)

            class_check = Macro(
                self.qom_cpu.class_macro(),
                args = ["klass"],
                text = "OBJECT_CLASS_CHECK(%s, (klass), %s)" % (
                    cpu_class.name,
                    type_arch_cpu.name
                )
            )
            class_check.extra_references = [type_arch_cpu]
            hdr.add_type(class_check)

            cpu = Macro(
                qtn.for_macros,
                args = ["obj"],
                text = "OBJECT_CHECK(%s, (obj), %s)" % (
                    arch_cpu.name,
                    type_arch_cpu.name
                )
            )
            cpu.extra_references = [type_arch_cpu]
            hdr.add_type(cpu)

            get_class = Macro(
                self.qom_cpu.get_class_macro(),
                args = ["obj"],
                text = "OBJECT_GET_CLASS(%s, (obj), %s)" % (
                    cpu_class.name,
                    type_arch_cpu.name
                )
            )
            get_class.extra_references = [type_arch_cpu]
            hdr.add_type(get_class)

            helper_c = self.gen_files["helper.c"]

            tlb_fill = Type["tlb_fill"].gen_definition()
            self.g.gen_tlb_fill(tlb_fill)
            handle_mmu_fault = handle_mmu_fault_decl.gen_definition()
            self.g.gen_handle_mmu_fault(handle_mmu_fault)

            helper_c.add_type(handle_mmu_fault)
            helper_c.add_type(tlb_fill)

        def gen_instruction_funcs_file():
            h = self.gen_files["translate.inc.c"]

            h.add_type(
                Enumeration(
                    "br_enum",
                    {
                        "BS_NONE": 0,
                        "BS_STOP": 1,
                        "BS_BRANCH": 2,
                        "BS_EXCP": 3
                    }
                )
            )

            disas_context = Structure("DisasContext")
            disas_context.append_field_t_s("TranslationBlock", "tb",
                pointer = True
            )
            disas_context.append_field_t_s("uint64_t", "pc")
            disas_context.append_field_t_s("uint64_t", "opcode")
            disas_context.append_field_t_s("int", "bstate")
            disas_context.append_field_t_s("bool", "singlestep_enabled")
            h.add_type(disas_context)

            Header["exec/cpu_ldst.h"].add_reference(disas_context)

            set_pc = Function(
                name = "set_pc",
                ret_type = Type["void"],
                args = [Type["uint64_t"].gen_var("val")],
                static = True,
                inline = True
            )
            self.g.gen_set_pc(set_pc, h.global_variables["pc"])
            h.add_type(set_pc)

        def gen_vmstate_description():
            src = self.gen_files["machine.c"]
            cpu_arch_state = Type[self.qom_cpu.struct_state_name()]
            vmstate = self.qom_cpu.gen_vmstate_var(cpu_arch_state)
            src.add_global_variable(vmstate)

        def gen_target_makefile(src):
            target_makefile = join(src, self.target_folder, "Makefile.objs")
            with open(target_makefile, "w") as mkf:
                mkf.write("obj-y +=")
                for f in self.gen_files.values():
                    if type(f) is Source:
                        mkf.write(' ' + splitext(basename(f.path))[0] + ".o")
                mkf.write("\n")

        def gen_helper_header(src):
            with open(join(src, self.target_folder, "helper.h"), "w") as h:
                h.write("DEF_HELPER_1(debug, void, env)\n")
                h.write("DEF_HELPER_1(illegal, void, env)\n")

        def gen_translation_code():
            src = self.gen_files["translate.c"]
            qom_cpu = self.qom_cpu

            decode_opc = Function(
                name = "decode_opc",
                ret_type = Type["int"],
                args = [
                    Type[qom_cpu.struct_name].gen_var("cpu",
                        pointer = True
                    ),
                    Type["DisasContext"].gen_var("ctx", pointer = True)
                ],
                static = True
            )

            if get_vp("Init cpu_env in arch"):
                cpu_env = src.global_variables["cpu_env"]
            else:
                cpu_env = Header["tcg.h"].global_variables["cpu_env"]
            self.g.gen_decode_opc(
                decode_opc,
                src.global_variables["cpu_pc"],
                cpu_env
            )
            src.add_type(decode_opc)

            cpu_arch_state = Type[qom_cpu.struct_state_name()]

            if get_vp("gen_intermediate_code arg1 is generic"):
                arg1 = Type["CPUState"].gen_var("cs", pointer = True)
            else:
                arg1 = cpu_arch_state.gen_var("env", pointer = True)
            gen_int_code_def = Function(
                name = "gen_intermediate_code.definition",
                args = [
                    arg1,
                    Type["TranslationBlock"].gen_var("tb", pointer = True)
                ]
            )
            self.g.gen_gen_intermediate_code(
                gen_int_code_def,
                src.global_variables["cpu_pc"],
                cpu_env
            )
            gen_int_code_def.declaration = Type["gen_intermediate_code"]
            src.add_type(gen_int_code_def)

            restore_state = Function(
                name = "restore_state_to_opc",
                args = [
                    cpu_arch_state.gen_var("env", pointer = True),
                    Type["TranslationBlock"].gen_var("tb", pointer = True),
                    Type["target_ulong"].gen_var("data", pointer = True)
                 ]
            )
            self.g.gen_restore_state_to_opc(restore_state)
            src.add_type(restore_state)

        def gen_disas():
            disas = self.gen_files[self.target_name + ".c"]

            type_by_specifier_and_length = {
                ('d', 'i'): {
                    None: "int",
                    'hh': "signed char",
                    'h': "short int",
                    'l': "long int",
                    'll': "long long int",
                    'j': "intmax_t",
                    'z': "size_t",
                    't': "ptrdiff_t"
                },
                ('u', 'o', 'x', 'X'): {
                    None: "unsigned", # "unsigned int"
                    'hh': "unsigned char",
                    'h': "unsigned short int",
                    'l': "unsigned long int",
                    'll': "unsigned long long int",
                    'j': "uintmax_t",
                    'z': "size_t",
                    't': "ptrdiff_t"
                },
                ('f', 'F', 'e', 'E', 'g', 'G', 'a', 'A'): {
                    None: "double",
                    'L': "long double"
                },
                ('c',): {
                    None: "char", # "int"
                    'l': "wint_t"
                },
                ('s',): {
                    None: "const char*", # "char*"
                    'l': "wchar_t*"
                },
                ('p',): {
                    None: "void*"
                },
                ('n',): {
                    None: "int*",
                    'hh': "signed char*",
                    'h': "short int*",
                    'l': "long int*",
                    'll': "long long int*",
                    'j': "intmax_t*",
                    'z': 'size_t*',
                    't': "ptrdiff_t*"
                }
            }
            ftr = {}
            for specifiers, info in type_by_specifier_and_length.items():
                subftr = {}
                for length, type_name in info.items():
                    if type_name.endswith('*'):
                        subftr[length] = Pointer(Type[type_name[:-1]])
                    else:
                        subftr[length] = Type[type_name]
                for specifier in specifiers:
                    ftr[specifier] = subftr

            added = {}
            for r in self.reg_groups:
                reg_var = Type["const char"].gen_var(
                    r.name,
                    pointer = True,
                    initializer = Initializer(
                        code = ('{\n    "' +
                            '",\n    "'.join(r.name for r in r.regs) + '"\n}'
                        )
                    ),
                    static = True,
                    array_size = len(r)
                )

                disas.add_global_variable(reg_var)

            re_spec = compile("(?<!%)(?:%%)*(%(?:"
                "(?:[-+ #0]{0,5})"         # flags
                "(?:\d+|\*)?"              # width
                "(?:\.(?:\d+|\*))?"        # precision
                "(hh|h|l|ll|j|z|t|L)?"     # length
                "([diuoxXfFeEgGaAcspn])))" # specifier
            )
            for n, v in self.name_to_format.items():
                if v[1] is None:
                    continue
                arg_count = n.count(',') + 1
                if added.get(v[1]) is None:
                    if v[0] is not None:
                        spec_m = re_spec.search(v[0])
                        if spec_m:
                            length = spec_m.group(2)
                            specifier = spec_m.group(3)
                            try:
                                ret_type = ftr[specifier][length]
                            except KeyError:
                                raise Exception('Illegal format specifier "' +
                                    spec_m.group(1) + '"'
                                )
                        else:
                            raise Exception(
'Format specifier not found in string "' + v[0] + '"'
                            )
                        args = []
                    else:
                        args = [
                            Type["void"].gen_var("stream", pointer = True),
                            Type["fprintf_function"].gen_var("fpr")
                        ]
                        ret_type = Type["void"]
                    if arg_count == 1:
                        args += [ Type["uint64_t"].gen_var("arg") ]
                    else:
                        args += [ Type["uint64_t"].gen_var("arg" + str(i))
                            for i in range(0, arg_count)
                        ]
                    f = Function(
                        name = v[1],
                        ret_type = ret_type,
                        args = args,
                        static = True
                    )
                    if v[0] is not None:
                        self.g.gen_helper_disas_write(f)
                    disas.add_type(f)
                    added[v[1]] = (arg_count, v[0] is None)
                elif added[v[1]] != (arg_count, v[0] is None):
                    def xstr(a):
                        return "None" if a is None else '"' + a + '"'
                    raise Exception(
'"%s": (%s, "%s") try to use function with another number of arguments or '
"argument type than before" % (n, xstr(v[0]), v[1])
                    )

            disas_def = (Type["print_insn_" + self.target_name].
                gen_definition()
            )
            self.g.gen_print_ins(disas_def)
            disas.add_type(disas_def)

        self.instr_tree_root = build_instruction_tree(self.instructions,
            verbose = verbose
        )

        self.g = TargetCodeGenerator(self)

        self.target_folder = get_vp("target folder") + self.target_name + sep

        abs_target_folder = join(qemu_src, self.target_folder)
        if not exists(abs_target_folder):
            makedirs(abs_target_folder)

        self.gen_files = OrderedDict()
        for fname in ["cpu.h", "translate.inc.c", "cpu.c", "helper.c",
            "machine.c", "translate.c"
        ]:
            path = join(self.target_folder, fname)
            if fname[-1] == "h" or fname.find(".inc.c") != -1:
                self.gen_files[fname] = Header(path)
            else:
                self.gen_files[fname] = Source(path)

        create_default_config(qemu_src)
        update_configure(qemu_src)
        update_archinit(qemu_src)
        update_bfd(qemu_src)
        gen_target_files()
        gen_vmstate_description()
        gen_target_makefile(qemu_src)
        self.gen_qom_model(self.gen_files, self.g)
        gen_instruction_funcs_file()
        gen_translation_code()
        gen_helper_header(qemu_src)

        abs_disas_folder = join(qemu_src, "disas")
        disas_name = self.target_name + ".c"
        self.gen_files[disas_name] = Source(join(abs_disas_folder, disas_name))

        patch_makefile(
            join(abs_disas_folder, "Makefile.objs"),
            self.target_name + ".o",
            "common-obj",
            "$(CONFIG_" + self.target_name.upper() + "_DIS)"
        )

        gen_disas()

    def gen_all(self, qemu_src,
        with_chunk_graph = False,
        with_debug_comments = False,
        verbose = False
    ):
        self.gen_target_code(qemu_src, verbose)

        for f in self.gen_files.values():
            path = join(qemu_src, f.path)
            with open(path, mode = "wb", encoding = "utf-8") as f_writer:
                sf = f.generate()

                if with_chunk_graph:
                    sf.gen_chunks_gv_file(f.path + ".chunks.gv")

                sf.generate(f_writer, gen_debug_comments = with_debug_comments)
