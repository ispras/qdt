__all__ = [
    "CPUType"
  , "CPUInfo"
]


from os import (
    makedirs,
    remove,
    rename
)
from os.path import (
    sep,
    isfile,
    isdir,
    join,
    basename,
    splitext
)
from codecs import (
    open
)
from .qom import (
    QOMCPU
)
from source import (
    Header,
    Source,
    Type,
    Initializer,
    Function,
    Structure,
    Pointer,
    Macro,
    TypeAlias,
    Enumeration
)
from .version import (
    get_vp
)
from .instruction import (
    interval_to_bits
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
    BYTE_SIZE,
    SUPPORTED_READ_SIZES
)
from .qom_desc import (
    describable
)
from common import (
    mlget as _,
    execfile,
    path2tuple,
    ee
)
from traceback import (
    print_exc
)
from itertools import (
    combinations
)


SHOW_INTERSECTION_WARNINGS = ee("QDT_SHOW_INTERSECTION_WARNINGS")


spec_and_len2typename = {
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


re_format_specifier = compile("(?<!%)(?:%%)*(%(?:"
    "(?:[-+ #0]{0,5})"         # flags
    "(?:\d+|\*)?"              # width
    "(?:\.(?:\d+|\*))?"        # precision
    "(hh|h|l|ll|j|z|t|L)?"     # length
    "([diuoxXfFeEgGaAcspn])))" # specifier
)


class InstructionTreeNode(object):

    def __init__(self, opcode = None):
        self.instruction = None
        self.opcode = opcode
        self.subtree = OrderedDict()
        self.reads_desc = []


def common_bits_for_opcodes(instructions):
    "Finds bit numbers occupied by opcodes in all instructions."

    return instructions[0].opcode_bits.intersection(
        *[i.opcode_bits for i in instructions[1:]]
    )


def bits_to_intervals(bits):
    """ Converts bit numbers to bit intervals.

:returns: list of tuples: [(off_1, len_1), ..., (off_k, len_k), ...]
    """

    if not bits:
        return []

    bit_numbers = sorted(bits)
    result = []
    offset = prev_bit = bit_numbers[0]
    length = 1

    for bit in bit_numbers[1:]:
        if bit - prev_bit == 1:
            length += 1
        else:
            result.append((offset, length))
            offset = bit
            length = 1

        prev_bit = bit

    result.append((offset, length))
    return result


def split_intervals(intervals, read_size):
    "Splits intervals by read_size."

    new_intervals = []

    for i in intervals:
        cur_offset, length = i

        if (cur_offset // read_size != (cur_offset + length - 1) // read_size):
            while length > 0:
                new_offset = (cur_offset // read_size + 1) * read_size
                new_length = min(new_offset - cur_offset, length)

                new_intervals.append((cur_offset, new_length))

                length -= new_offset - cur_offset
                cur_offset = new_offset
        else:
            new_intervals.append(i)

    return new_intervals


def build_instruction_tree(node, instructions, read_size,
        checked_bits = set(),
        show_subtree_warnings = True
    ):
    min_len = min(len(i) for i in instructions)
    # temporary info for reads description calculation
    node.limit_read = min_len

    common_bits = common_bits_for_opcodes(instructions)
    unchecked_bits = common_bits - checked_bits
    unchecked_opcs = split_intervals(
        bits_to_intervals(unchecked_bits), read_size
    )

    for opc in unchecked_opcs:
        opcs = [i.get_opcode_part(opc) for i in instructions]

        if len(set(opcs)) > 1:
            break
    else:
        if len(instructions) == 1:
            i = instructions[0]

            for opc in unchecked_opcs:
                node.opcode = opc
                key = i.get_opcode_part(opc)
                node.subtree[key] = n = InstructionTreeNode()
                node = n
                # temporary info for reads description calculation
                node.limit_read = min_len

            node.instruction = i
            return
        else:
            max_len = max(len(i) for i in instructions)
            min_len_bits = interval_to_bits((0, min_len))

            for i in instructions:
                for f in i.fields:
                    field_bits = interval_to_bits((f.offset, f.length))
                    unchecked_bits = (field_bits - checked_bits) & min_len_bits
                    unchecked_opcs = split_intervals(
                        bits_to_intervals(unchecked_bits), read_size
                    )

                    if not unchecked_opcs:
                        continue

                    for opc in unchecked_opcs:
                        opcs = [j.get_opcode_part(opc) for j in instructions]

                        if len(set(opcs)) > 1:
                            break
                    else:
                        # not found `opc` yet
                        continue
                    # found `opc`
                    break
                else:
                    # not found `opc` yet
                    continue
                # found `opc`
                break
            else:
                raise RuntimeError("Unresolved conflict in instructions:"
                    "\n    " + "\n    ".join(
                        "{1:<{0}} {2}".format(max_len, i.string, i.comment)
                        for i in instructions
                    )
                )

            pe_flag = False

            for i1, i2 in combinations(instructions, 2):
                i1b = i1.opcode_bits
                i2b = i2.opcode_bits

                if not (i1b <= i2b or i1b >= i2b):
                    pe_flag = True
                    break

            if pe_flag:
                print("Potential error: bit check order affects instruction"
                    " parse tree for instructions:\n    " + "\n    ".join(
                        "{1:<{0}} {2}".format(max_len, i.string, i.comment)
                        for i in instructions
                    )
                )

            if (not pe_flag
                and show_subtree_warnings
                and SHOW_INTERSECTION_WARNINGS
            ):
                print("Warning: arguments and opcode intersect in instructions"
                    ":\n    " + "\n    ".join(
                        "{1:<{0}} {2}".format(max_len, i.string, i.comment)
                        for i in instructions
                    )
                )

            show_subtree_warnings = False

    node.opcode = opc
    new_checked_bits = checked_bits | interval_to_bits(opc)

    subtree = defaultdict(list)

    for i in instructions:
        key = i.get_opcode_part(opc)
        if key is None:
            key = "default"
        subtree[key].append(i)

    for key, instructions in sorted(subtree.items()):
        node.subtree[key] = n = InstructionTreeNode()
        build_instruction_tree(n, instructions, read_size,
            checked_bits = (
                checked_bits if key == "default" else new_checked_bits
            ),
            show_subtree_warnings = show_subtree_warnings
        )


def calc_node_reads_desc(need_read, already_read, limit_read):
    if need_read <= already_read:
        return []

    result = []

    for r_size in reversed(SUPPORTED_READ_SIZES):
        while need_read > already_read and already_read + r_size <= limit_read:
            result.append((already_read, r_size))
            already_read += r_size

    return result


def fill_tree_reads_desc(node, read_size, already_read = 0):
    ins = node.instruction

    if ins is None:
        opc = node.opcode

        desc = calc_node_reads_desc(opc[0] + opc[1], already_read,
            node.limit_read
        )

        if desc:
            node.reads_desc = desc
            already_read = desc[-1][0] + desc[-1][1]

        for subnode in node.subtree.values():
            fill_tree_reads_desc(subnode, read_size, already_read)
    else:
        node.reads_desc = calc_node_reads_desc(len(ins), already_read,
            node.limit_read
        )

    del node.limit_read


def add_global_array(reg, arr_name, f):
    names_array = Pointer(Type["const char"])(arr_name,
        initializer = Initializer(
            code = '{\n    "%s"\n}' % (
                '",\n    "'.join(reg.reg_names)
            )
        ),
        static = True,
        array_size = reg.len
    )
    f.add_global_variable(names_array)
    return names_array


@describable
class CPUType(QOMCPU):
    __attribute_info__ = OrderedDict([
        ("target_bigendian", {
            "short": _("Target is big-endian"),
            "input": bool
        }),
        ("target_long_bits", {
            "short": _("Size of target long in bits"),
            "input": int
        }),
        ("target_page_bits", {
            "short": _("Size of target page in bits"),
            "input": int
        }),
        ("target_phys_addr_space_bits", {
            "short": _("Size of target physical address space in bits"),
            "input": int
        }),
        ("target_virt_addr_space_bits", {
            "short": _("Size of target virtual address space in bits"),
            "input": int
        }),
        ("nb_mmu_modes", { "short": _("Number of MMU modes"), "input": int }),
        ("info_path", {
            "short": _("Path to file with CPU information"),
            "input": str
        })
    ])

    def __init__(self, name, directory,
        target_bigendian = False,
        target_long_bits = 32,
        target_page_bits = 12,
        target_phys_addr_space_bits = 32,
        target_virt_addr_space_bits = 32,
        nb_mmu_modes = 1,
        info_path = None
    ):
        """ CPU description.

    :param name:
        name of CPU

    :param directory:
        name of Target architecture
        """

        super(CPUType, self).__init__(name, directory)

        self.target_bigendian = target_bigendian

        self.attributes = {
            "TARGET_LONG_BITS": target_long_bits,
            "TARGET_PAGE_BITS": target_page_bits,
            "TARGET_PHYS_ADDR_SPACE_BITS": target_phys_addr_space_bits,
            "TARGET_VIRT_ADDR_SPACE_BITS": target_virt_addr_space_bits,
            "NB_MMU_MODES": nb_mmu_modes
        }

        self.info_path = info_path

    def co_gen(self, src,
        with_chunk_graph = False,
        with_debug_comments = False,
        **_
    ):
        import cpu_imports
        loaded = dict(cpu_imports.__dict__)
        try:
            execfile(join(self.info_path), loaded)
        except:
            print_exc()
            raise RuntimeError(
                "Cannot load CPU info from '%s'" % self.info_path
            )

        for v in loaded.values():
            if isinstance(v, CPUInfo):
                info = v
                break
        else:
            raise RuntimeError(
                "Script '%s' does not define a CPU info" % self.info_path
            )

        self.registers = info.registers
        self.pc_register = info.pc_register

        for reg in self.registers:
            self.add_state_field_h("uint%d_t" % (reg.size * BYTE_SIZE),
                reg.name,
                num = reg.len,
                save = True
            )

        self.name_to_format = info.name_to_format
        self.instructions = info.instructions
        self.read_size = info.read_size * BYTE_SIZE
        self.reg_types = info.reg_types

        if self.read_size not in SUPPORTED_READ_SIZES:
            raise RuntimeError(
                "Valid `read_size` values are %s bytes" % (
                    ", ".join(i / BYTE_SIZE for i in SUPPORTED_READ_SIZES)
                )
            )

        for i in self.instructions:
            i.split_operands_fill_offsets(self.read_size)

        lens = [len(i) for i in self.instructions]
        try:
            min_size = min(lens)
            max_size = max(lens)
        except ValueError:
            min_size = 0
            max_size = 0
        instr_size_is_fixed = min_size == max_size

        self.min_instr_size = min_size

        print("{arch} is a {endianess}-endian {is_fixed} instruction size"
            " architecture with {size_info}".format(
            arch = self.target_name.upper(),
            endianess = "big" if self.target_bigendian else "little",
            is_fixed = "fixed" if instr_size_is_fixed else "variable",
            size_info = ("size = %d" % min_size if instr_size_is_fixed else
                "min_size = %d and max_size = %d" % (min_size, max_size)
            )
        ))

        self.reg_types()

        yield True

        yield self._co_gen_target_code(src)

        for f in self.gen_files.values():
            path = join(src, f.path)
            with open(path, mode = "wb", encoding = "utf-8") as f_writer:
                sf = f.generate(inherit_references = isinstance(f, Header))

                yield True

                if with_chunk_graph:
                    yield True
                    sf.gen_chunks_gv_file(path + ".chunks.gv")

                yield True

                sf.generate(f_writer, gen_debug_comments = with_debug_comments)

        path = self.gen_files["translate.inc.c"].path
        old_path = join(src, path)
        new_path = join(src, path[:-1] + "i3s.c")

        if isfile(new_path):
            remove(new_path)

        rename(old_path, new_path)

        if with_chunk_graph:
            new_chunk_path = new_path + ".chunks.gv"

            if isfile(new_chunk_path):
                remove(new_chunk_path)

            rename(old_path + ".chunks.gv", new_chunk_path)

        yield True

        with open(join(src, old_path), "w") as f:
            f.write("""
/* autogenerated temporary translate.inc.c */
#ifndef INCLUDE_TEMPORARY_TRANSLATE_INC_C
#define INCLUDE_TEMPORARY_TRANSLATE_INC_C

#define tcg TCGv
#include "translate.inc.i3s.c"

#endif /* INCLUDE_TEMPORARY_TRANSLATE_INC_C */
""")

    def _co_gen_target_code(self, src):
        if self.instructions:
            self.instruction_tree_root = n = InstructionTreeNode()
            build_instruction_tree(n, self.instructions, self.read_size)
            fill_tree_reads_desc(n, self.read_size)
        else:
            self.instruction_tree_root = None

        yield True

        self.g = TargetCodeGenerator(self)

        target_folder = get_vp("target folder") + self.target_name + sep
        abs_target_folder = join(src, target_folder)

        if not isdir(abs_target_folder):
            makedirs(abs_target_folder)

        yield True

        create_default_config(src, self.target_name)

        yield True

        patch_configure(src, self.target_bigendian, self.target_name)

        yield True

        patch_arch_init_header(src, self.target_name)

        yield True

        patch_arch_init_source(src, self.target_name)

        yield True

        patch_disas_header(src, self.print_insn_name(), self.bfd_arch_name())

        yield True

        patch_poison_header(src, self.target_arch(), self.config_arch_dis())

        yield True

        self.gen_files = OrderedDict()
        file_list = ["cpu.h", "translate.inc.c", "cpu.c", "helper.c",
            "machine.c", "translate.c"
        ]
        if get_vp("cpu-param header exists"):
            file_list = ["cpu-param.h"] + file_list
        for file_name in file_list:
            path = join(target_folder, file_name)
            if file_name[-1] == "h" or file_name.find(".inc.c") != -1:
                file_ = Header(path)
            else:
                file_ = Source(path)
            self.gen_files[file_name] = file_

            name = file_name.replace(".", "_").replace("-", "_")
            getattr(self, "_gen_" + name)(file_)

            yield True

        self._gen_target_makefile(join(abs_target_folder, "Makefile.objs"))

        yield True

        self._gen_helper_h(join(abs_target_folder, "helper.h"))

        yield True

        abs_disas_folder = join(src, "disas")
        disas_name = self.target_name + ".c"
        disas = Source(join(abs_disas_folder, disas_name))
        self.gen_files[disas_name] = disas

        yield True

        patch_makefile(
            join(abs_disas_folder, "Makefile.objs"),
            self.target_name + ".o",
            "common-obj",
            "$(" + self.config_arch_dis() + ")"
        )

        yield True

        self._gen_disas(disas)

    def _gen_cpu_c(self, c):
        cpu_class = Type["CPUClass"]
        type_info_type = Type["TypeInfo"]
        fn_name = self.func_name

        for func in ["reset", "disas_set_info", "set_pc", "class_by_name",
            "has_work"
        ]:
            f = getattr(cpu_class, func).gen_callback(fn_name(func),
                static = True
            )
            getattr(self.g, "gen_cpu_" + func)(f)
            c.add_type(f)

        gdb_read_register = cpu_class.gdb_read_register.gen_callback(
            fn_name("gdb_read_register"),
            static = True
        )
        self.g.gen_cpu_gdb_rw_register(
            gdb_read_register,
            "TODO: implement gdb_read_register"
        )
        c.add_type(gdb_read_register)

        gdb_write_register = cpu_class.gdb_write_register.gen_callback(
            fn_name("gdb_write_register"),
            static = True
        )
        self.g.gen_cpu_gdb_rw_register(
            gdb_write_register,
            "TODO: implement gdb_write_register"
        )
        c.add_type(gdb_write_register)

        realizefn = Type["DeviceRealize"].type.use_as_prototype(
            fn_name("realizefn"),
            static = True
        )
        self.g.gen_cpu_realizefn(realizefn)
        c.add_type(realizefn)

        if get_vp("cpu_arch_init exists"):
            cpu_init_def = Type[self.cpu_init_name()].gen_definition()
            self.g.gen_cpu_init(cpu_init_def)
            c.add_type(cpu_init_def)

        cpu_initfn = type_info_type.instance_init.gen_callback(
            fn_name("initfn"),
            static = True
        )
        self.g.gen_cpu_initfn(cpu_initfn)
        c.add_type(cpu_initfn)

        cpu_class_init = type_info_type.class_init.gen_callback(
            fn_name("class_init"),
            static = True
        )
        num_core_regs = sum(r.len or 1 for r in self.registers)
        self.g.gen_cpu_class_init(cpu_class_init, num_core_regs,
            self.gen_files["cpu.h"].global_variables[
                "vmstate_" + self.qtn.for_id_name
            ]
        )
        c.add_type(cpu_class_init)

        type_info = type_info_type(self.type_info_name(),
            initializer = Initializer(
                {
                    "name": Type[self.qtn.type_macro],
                    "parent": Type["TYPE_CPU"],
                    "instance_size": "sizeof(%s)" % self.struct_name,
                    "instance_init": cpu_initfn,
                    "class_size": "sizeof(%s)" % self.struct_class_name(),
                    "class_init": cpu_class_init
                },
                used_types = [
                    Type[self.struct_name],
                    Type[self.struct_class_name()]
                ]
            ),
            static = True,
            const = True
        )
        c.add_global_variable(type_info)

        cpu_register_types = self.gen_register_types_fn(type_info)
        c.add_type(cpu_register_types)

        type_init_usage_init = Initializer({ "function": cpu_register_types })

        c.add_type(
            Type["type_init"].gen_type(initializer = type_init_usage_init)
        )

    def _gen_cpu_h(self, h):
        fn_name = self.func_name

        # "cpu.h" header does not require anything from "cpu-all.h" header.
        # "exec.c" source file include "cpu.h" header and require type
        # "TARGET_PAGE_SIZE".
        # Only "cpu.h" header can satisfy the dependency.
        exec_c = Source("exec.c", locked = True)
        exec_c.add_reference(Type["TARGET_PAGE_SIZE"])
        exec_c.add_inclusion(h)

        if not get_vp("cpu-param header exists"):
            for name, value in self.attributes.items():
                m = Macro(name, text = value)
                h.add_type(m)

            Header["exec/cpu-defs.h"].add_reference(Type["TARGET_LONG_BITS"])

        cpu_arch_state = self.gen_state()
        h.add_type(cpu_arch_state)

        arch_cpu_fields = [
            Type["CPUState"]("parent_obj"),
            cpu_arch_state("env")
        ]
        if get_vp("CPUNegativeOffsetState exists"):
            arch_cpu_fields.insert(1, Type["CPUNegativeOffsetState"]("neg"))
        arch_cpu = Structure(self.struct_name, *arch_cpu_fields)
        h.add_type(arch_cpu)

        if get_vp("typedef ArchCPU"):
            h.add_type(TypeAlias(arch_cpu, "ArchCPU"))

        if get_vp("typedef CPUArchState"):
            arch_state = TypeAlias(cpu_arch_state, "CPUArchState")
        else:
            arch_state = Macro("CPUArchState",
                text = "struct " + cpu_arch_state.c_name
            )
        h.add_type(arch_state)
        Header["tcg.h"].add_reference(arch_state)
        Header["exec/cpu-all.h"].add_references([
            arch_state,
            Type["TARGET_LONG_SIZE"]
        ])
        Header["exec/exec-all.h"].add_reference(arch_state)

        h.add_global_variable(Type["VMStateDescription"](
            "vmstate_" + self.qtn.for_id_name,
            const = True
        ))

        if not get_vp("env_archcpu exists"):
            env_get_cpu = Function(
                name = self.env_get_cpu_name(),
                ret_type = Pointer(arch_cpu),
                args = [ Pointer(cpu_arch_state)("env") ],
                static = True,
                inline = True
            )
            self.g.gen_cpu_env_get_cpu(env_get_cpu)
            h.add_type(env_get_cpu)

        h.add_type(Enumeration([("EXCP_ILLEGAL", 1)]))

        if get_vp("CPUClass has tlb_fill field"):
            h.add_type(
                Type["CPUClass"].tlb_fill.gen_callback(fn_name("tlb_fill"))
            )
        else:
            h.add_type(
                Function(
                    name = fn_name("handle_mmu_fault"),
                    ret_type = Type["int"],
                    args = [
                        Pointer(Type["CPUState"])("cs"),
                        Type["vaddr"]("address")
                    ] +
                    (
                        [ Type["int"]("size") ] if get_vp(
                            "tlb_fill has SIZE argument"
                        )
                        else
                        []
                    ) +
                    [
                        Type["int"]("rw"),
                        Type["int"]("mmu_idx")
                    ]
                )
            )

        if not get_vp("env_cpu exists"):
            h.add_type(
                Macro("ENV_GET_CPU",
                    args = [ "e" ],
                    text = "CPU(%s(e))" % env_get_cpu.c_name
                )
            )

        if not get_vp("ENV_OFFSET is generic"):
            h.add_type(
                Macro("ENV_OFFSET",
                    text = "offsetof(%s, env)" % arch_cpu.c_name
                )
            )

        cpu_mmu_index = Function(
            name = "cpu_mmu_index",
            ret_type = Type["int"],
            args = [
                Pointer(cpu_arch_state)("env"),
                Type["bool"]("ifetch")
            ],
            static = True,
            inline = True
        )
        self.g.gen_cpu_mmu_index(cpu_mmu_index)
        h.add_type(cpu_mmu_index)

        get_tb_cpu_state = Function(
            name = "cpu_get_tb_cpu_state",
            args = [
                Pointer(cpu_arch_state)("env"),
                Pointer(Type["target_ulong"])("pc"),
                Pointer(Type["target_ulong"])("cs_base"),
                Pointer(Type["uint32_t"])("flags")
            ],
            static = True,
            inline = True
        )
        self.g.gen_cpu_get_tb_cpu_state(get_tb_cpu_state)
        h.add_type(get_tb_cpu_state)

        type_arch_cpu = Macro(self.qtn.type_macro,
            text = '"%s"' % self.qtn.name
        )
        h.add_type(type_arch_cpu)

        cpu_class = Structure(self.struct_class_name(),
            Type["CPUClass"]("parent_class"),
            Type["DeviceRealize"]("parent_realize"),
            Function(
                args = [ Pointer(Type["CPUState"])("cpu") ]
            )("parent_reset")
        )
        h.add_type(cpu_class)

        class_check = Macro(self.class_macro(),
            args = [ "klass" ],
            text = "OBJECT_CLASS_CHECK(%s, (klass), %s)" % (
                cpu_class.c_name,
                type_arch_cpu.c_name
            )
        )
        class_check.extra_references = {type_arch_cpu}
        h.add_type(class_check)

        cpu = Macro(self.qtn.for_macros,
            args = [ "obj" ],
            text = "OBJECT_CHECK(%s, (obj), %s)" % (
                arch_cpu.c_name,
                type_arch_cpu.c_name
            )
        )
        cpu.extra_references = {type_arch_cpu}
        h.add_type(cpu)

        get_class = Macro(self.get_class_macro(),
            args = [ "obj" ],
            text = "OBJECT_GET_CLASS(%s, (obj), %s)" % (
                cpu_class.c_name,
                type_arch_cpu.c_name
            )
        )
        get_class.extra_references = {type_arch_cpu}
        h.add_type(get_class)

        if get_vp("CPU_RESOLVING_TYPE exists"):
            cpu_resolving_type = Macro("CPU_RESOLVING_TYPE",
                text = type_arch_cpu.c_name
            )
            cpu_resolving_type.extra_references = {type_arch_cpu}
            h.add_type(cpu_resolving_type)

        if get_vp("cpu_arch_init exists"):
            h.add_type(
                Macro("cpu_init",
                    args = [ "cpu_model" ],
                    text = "CPU(%s(cpu_model))" % self.cpu_init_name()
                )
            )
        elif get_vp("cpu_init exists"):
            cpu_init = Macro("cpu_init",
                args = [ "cpu_model" ],
                text = "cpu_generic_init(%s, cpu_model)" % (
                    type_arch_cpu.c_name
                )
            )
            cpu_init.extra_references = {type_arch_cpu}
            h.add_type(cpu_init)

        cpu_class = Type["CPUClass"]

        h.add_types([
            cpu_class.do_interrupt.gen_callback(fn_name("do_interrupt")),
            cpu_class.get_phys_page_debug.gen_callback(
                fn_name("get_phys_page_debug")
            ),
            cpu_class.dump_state.gen_callback(fn_name("dump_state")),
            Function(name = self.tcg_init_name())
        ])

        if get_vp("cpu_arch_init exists"):
            h.add_type(
                Function(
                    name = self.cpu_init_name(),
                    ret_type = Pointer(Type[self.struct_name]),
                    args = [ Pointer(Type["const char"])("cpu_model") ]
                )
            )

    def _gen_cpu_param_h(self, h):
        for name, value in self.attributes.items():
            m = Macro(name, text = value)
            h.add_type(m)

    def _gen_disas(self, c):
        # register own realization of "bfd_getb64"
        self.g.gen_disas_bfd_getb64(
            Function(
                name = "bfd_getb64",
                ret_type = Type["bfd_vma"],
                args = [ Pointer(Type["const bfd_byte"])("addr") ]
            )
        )

        spec_and_len2type = {}
        for specifiers, info in spec_and_len2typename.items():
            len2type = {}

            for length, typename in info.items():
                if typename.endswith('*'):
                    len2type[length] = Pointer(Type[typename[:-1]])
                else:
                    len2type[length] = Type[typename]

            for specifier in specifiers:
                spec_and_len2type[specifier] = len2type

        added = {}
        for reg in self.registers:
            if reg.len:
                add_global_array(reg, reg.name, c)

        for n, v in self.name_to_format.items():
            if v[1] is None:
                continue

            arg_count = n.count(',') + 1
            if added.get(v[1]) is None:
                if v[0] is not None:
                    f_spec_match = re_format_specifier.search(v[0])
                    if f_spec_match:
                        length = f_spec_match.group(2)
                        specifier = f_spec_match.group(3)
                        try:
                            ret_type = spec_and_len2type[specifier][length]
                        except KeyError:
                            raise Exception('Illegal format specifier "%s"' % (
                                f_spec_match.group(1)
                            ))
                    else:
                        raise Exception("Format specifier not found in string"
                            ' "%s"' % v[0]
                        )
                    args = []
                else:
                    args = [
                        Type["fprintf_function"]("fpr"),
                        Pointer(Type["void"])("stream")
                    ]
                    ret_type = Type["void"]

                if arg_count == 1:
                    args += [ Type["uint64_t"]("arg") ]
                else:
                    args += [ Type["uint64_t"]("arg" + str(i))
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

                c.add_type(f)

                added[v[1]] = (arg_count, v[0] is None)
            elif added[v[1]] != (arg_count, v[0] is None):
                raise Exception('"%s": (%r, "%s") try to use function with'
                    " another number of arguments or argument type than"
                    " before" % (n, v[0], v[1])
                )

        print_insn_def = Type[self.print_insn_name()].gen_definition()
        self.g.gen_disas_print_insn(print_insn_def)
        c.add_type(print_insn_def)

    def _gen_helper_c(self, h):
        fn_name = self.func_name

        if get_vp("tlb_fill exists"):
            tlb_fill = Type["tlb_fill"].gen_definition()
            self.g.gen_helper_tlb_fill(tlb_fill)
            h.add_type(tlb_fill)

        if get_vp("CPUClass has tlb_fill field"):
            cpu_tlb_fill = Type[
                fn_name("tlb_fill")
            ].gen_definition()
            self.g.gen_helper_cpu_tlb_fill(cpu_tlb_fill)
            h.add_type(cpu_tlb_fill)
        else:
            handle_mmu_fault = Type[
                fn_name("handle_mmu_fault")
            ].gen_definition()
            self.g.gen_helper_handle_mmu_fault(handle_mmu_fault)
            h.add_type(handle_mmu_fault)

        raise_exception = self.raise_exception()
        self.g.gen_helper_raise_exception(raise_exception)
        h.add_type(raise_exception)

        helper_debug = self.helper_debug()
        self.g.gen_helper_debug(helper_debug)
        h.add_type(helper_debug)

        helper_illegal = self.helper_illegal()
        self.g.gen_helper_illegal(helper_illegal)
        h.add_type(helper_illegal)

        Header["exec/helper-gen.h"].add_types([
            helper_debug.use_as_prototype("gen_" + helper_debug.name),
            helper_illegal.use_as_prototype("gen_" + helper_illegal.name)
        ])

        phys_page_debug_def = Type[
            fn_name("get_phys_page_debug")
        ].gen_definition()
        self.g.gen_helper_get_phys_page_debug(phys_page_debug_def)
        h.add_type(phys_page_debug_def)

        h.add_type(Type[fn_name("do_interrupt")].gen_definition())

    def _gen_helper_h(self, src):
        with open(src, "w") as h:
            h.write("DEF_HELPER_1(debug, void, env)\n")
            h.write("DEF_HELPER_1(illegal, void, env)\n")

    def _gen_machine_c(self, c):
        cpu_arch_state = Type[self.struct_state_name()]
        vmstate = self.gen_vmstate_var(cpu_arch_state)
        c.add_global_variable(vmstate)

    def _gen_target_makefile(self, src):
        with open(src, "w") as mkf:
            mkf.write("obj-y +=")

            for f in self.gen_files.values():
                if type(f) is Source:
                    mkf.write(" %s.o" % splitext(basename(f.path))[0])

            mkf.write("\n")

    def _gen_translate_c(self, c):
        if get_vp("Init cpu_env in arch"):
            cpu_env = Type["TCGv_env"]("cpu_env", static = True)
            c.add_global_variable(cpu_env)
            Header["exec/gen-icount.h"].add_reference(cpu_env)
        else:
            cpu_env = Header["tcg.h"].global_variables["cpu_env"]

        reg_vars = []
        for reg in self.registers:
            var = Type["TCGv"](reg.name, array_size = reg.len)
            c.add_global_variable(var)

            if reg.len:
                names_array = add_global_array(reg, reg.name + "_names", c)
            else:
                names_array = None

            reg_vars.append((reg, var, names_array))

        cpu_dump_state_def = Type[
            self.func_name("dump_state")
        ].gen_definition()
        self.g.gen_translate_cpu_dump_state(cpu_dump_state_def, reg_vars)
        c.add_type(cpu_dump_state_def)

        tcg_init_def = Type[self.tcg_init_name()].gen_definition()
        self.g.gen_translate_tcg_init(tcg_init_def, reg_vars, cpu_env)
        c.add_type(tcg_init_def)

        decode_opc = Function(
            name = "decode_opc",
            ret_type = Type["int"],
            args = [
                Pointer(Type[self.struct_name])("cpu"),
                Pointer(Type["DisasContext"])("ctx")
            ],
            static = True
        )
        self.g.gen_translate_decode_opc(decode_opc, cpu_env)
        c.add_type(decode_opc)

        cpu_arch_state_p = Pointer(Type[self.struct_state_name()])

        gen_int_code_args = [ Pointer(Type["TranslationBlock"])("tb") ]
        if get_vp("gen_intermediate_code arg1 is generic"):
            gen_int_code_args.insert(0, Pointer(Type["CPUState"])("cs"))
        else:
            gen_int_code_args.insert(0, cpu_arch_state_p("env"))
        if get_vp("gen_intermediate_code has max_insns argument"):
            gen_int_code_args.append(Type["int"]("max_insns"))
        gen_int_code_def = Function(
            name = "gen_intermediate_code.definition",
            args = gen_int_code_args
        )
        self.g.gen_translate_gen_intermediate_code(gen_int_code_def, cpu_env)
        gen_int_code_def.declaration = Type["gen_intermediate_code"]
        c.add_type(gen_int_code_def)

        restore_state_to_opc = Function(
            name = "restore_state_to_opc",
            args = [
                cpu_arch_state_p("env"),
                Pointer(Type["TranslationBlock"])("tb"),
                Pointer(Type["target_ulong"])("data")
            ]
        )
        self.g.gen_translate_restore_state_to_opc(restore_state_to_opc)
        c.add_type(restore_state_to_opc)

    def _gen_translate_inc_c(self, h):
        for reg in self.registers:
            h.add_global_variable(Type["tcg"](reg.name, array_size = reg.len))

        disas_context = Structure("DisasContext",
            Pointer(Type["TranslationBlock"])("tb"),
            Type["uint64_t"]("pc"),
            Type["uint64_t"]("opcode"),
            Type["int"]("bstate"),
            Type["bool"]("singlestep_enabled")
        )

        set_pc = Function(
            name = "set_pc",
            ret_type = Type["void"],
            args = [ Type["uint64_t"]("val") ],
            static = True,
            inline = True
        )
        self.g.gen_translate_inc_set_pc(set_pc,
            h.global_variables[self.pc_register]
        )

        h.add_types([
            Enumeration([
                ("BS_NONE", 0),
                ("BS_STOP", 1),
                ("BS_BRANCH", 2),
                ("BS_EXCP", 3)
            ]),
            disas_context,
            set_pc
        ])

        Header["exec/cpu_ldst.h"].add_reference(disas_context)


def create_default_config(src, target_name):
    default_config = join(src, "default-configs", target_name + "-softmmu.mak")

    with open(default_config, "w") as f:
        f.write("# Default configuration for %s-softmmu\n" % target_name)


def patch_configure(src, arch_bigendian, target_name):
    configure_path = join(src, "configure")

    with open(configure_path, "r") as f:
        lines = f.readlines()

    found_target_abi_dir = False
    target_in_config = "  %s)\n" % target_name
    inserted_target = False

    found_disas_config = False
    inserted_disas_config = False

    fixed_target_bigendian = False

    for i, line in enumerate(lines):
        if line == 'TARGET_ABI_DIR=""\n':
            found_target_abi_dir = True
        if line == "disas_config() {\n":
            found_disas_config = True

        if not fixed_target_bigendian and line == 'target_bigendian="no"\n':
            ind = i + get_vp("target_bigendian list offset")
            bigendian_list = lines[ind].strip()[:-1].split("|")
            if arch_bigendian:
                if target_name not in bigendian_list:
                    bigendian_list.append(target_name)
            else:
                if target_name in bigendian_list:
                    bigendian_list.remove(target_name)
            lines[ind] = "  " + "|".join(bigendian_list) + ")\n"
            fixed_target_bigendian = True

        if found_target_abi_dir and not inserted_target:
            if line == target_in_config:
                inserted_target = True
            elif line == "  *)\n":
                lines.insert(i,
                    """\
  {tn})
    TARGET_ARCH={tn}
    TARGET_BASE_ARCH={tn}
  ;;
""".format(tn = target_name)
                )
                inserted_target = True

        if found_disas_config and not inserted_disas_config:
            if line == target_in_config:
                inserted_disas_config = True
            if line == "  esac\n":
                lines.insert(i,
                    """\
  %s)
    disas_config "%s"
  ;;
""" % (target_name, target_name.upper())
                )
                inserted_disas_config = True

        if (    fixed_target_bigendian
            and inserted_target
            and inserted_disas_config
        ):
            break

    with open(configure_path, "w") as f:
        f.write("".join(lines))


def patch_arch_init_header(src, target_name):
    arch_init_header = join(src, "include", "sysemu", "arch_init.h")
    target_name_upper = target_name.upper()
    qemu_arch = "QEMU_ARCH_" + target_name_upper

    with open(arch_init_header, "r") as f:
        lines = f.readlines()

    index = 0
    str_qemu_arch = "    %s = " % qemu_arch
    found_arch_all = False

    for i, line in enumerate(lines):
        if found_arch_all:
            if str_qemu_arch in line:
                return
            elif line == "};\n":
                lines.insert(i, "%s(1 << %d),\n" % (str_qemu_arch, index))
                break
            else:
                index += 1
        elif line == "    QEMU_ARCH_ALL = -1,\n":
            found_arch_all = True

    with open(arch_init_header, "w") as f:
        f.write("".join(lines))


def patch_arch_init_source(src, target_name):
    arch_init_source = join(src, "arch_init.c")
    target_name_upper = target_name.upper()
    qemu_arch = "QEMU_ARCH_" + target_name_upper

    str_target = "TARGET_" + target_name_upper
    found_target_defines = False

    with open(arch_init_source, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if line[:19] == "#if defined(TARGET_":
            found_target_defines = True
            target_defines_start_idx = i

        if found_target_defines:
            if str_target in line:
                # target already in file
                return

            if line == "#endif\n":
                target_defines_end_idx = i
                break

    for i in range(target_defines_start_idx, target_defines_end_idx, 2):
        if str_target < lines[i].split("defined(")[1][:-1]:
            break
    else:
        i = target_defines_end_idx

    prefix = "el"
    if i == target_defines_start_idx:
        lines[i] = lines[i][:1] + "el" + lines[i][1:]
        prefix = ""

    lines.insert(i,
        """\
#%sif defined(%s)
#define QEMU_ARCH %s
""" % (prefix, str_target, qemu_arch)
    )

    with open(arch_init_source, "w") as f:
        f.write("".join(lines))


def patch_disas_header(src, print_insn_name, bfd_arch_name):
    Header[get_vp("disas header")].add_types([
        # not a real value
        Enumeration([(bfd_arch_name, 0)], enum_name = "bfd_architecture"),
        Function(
            name = print_insn_name,
            ret_type = Type["int"],
            args = [
                Type["bfd_vma"]("addr"),
                Pointer(Type["disassemble_info"])("info")
            ]
        )
    ])

    disas_header = join(src, "include", get_vp("disas header"))

    with open(disas_header, "r") as f:
        lines = f.readlines()

    str_bfd_arch_name = "  %s,\n" % bfd_arch_name
    inserted_bfd_arch = str_bfd_arch_name in lines

    found_print_insn = False
    print_insn = "int {:28}(bfd_vma, disassemble_info*);\n".format(
        print_insn_name
    )
    inserted_print_insn = print_insn in lines

    if inserted_bfd_arch and inserted_print_insn:
        return

    for i, line in enumerate(lines):
        if not inserted_bfd_arch and line == "  bfd_arch_last\n":
            lines.insert(i, str_bfd_arch_name)
            inserted_bfd_arch = True

        if not found_print_insn and "print_insn_" in line:
            found_print_insn = True
        if found_print_insn and not inserted_print_insn and line == "\n":
            lines.insert(i, print_insn)
            inserted_print_insn = True

        if inserted_bfd_arch and inserted_print_insn:
            break

    with open(disas_header, "w") as f:
        f.write("".join(lines))


def patch_poison_header(src, target_arch, config_arch_dis):
    poison_header = join(src, "include", "exec", "poison.h")

    with open(poison_header, "r") as f:
        lines = f.readlines()

    lines_group = 0

    poison_target_arch = "#pragma GCC poison " + target_arch + "\n"
    inserted_target_arch = poison_target_arch in lines

    poison_config_arch_dis = "#pragma GCC poison " + config_arch_dis + "\n"
    inserted_config_arch_dis = (poison_config_arch_dis in lines
        or not get_vp("config_arch_dis poisoned")
    )

    if inserted_target_arch and inserted_config_arch_dis:
        return

    for i, line in enumerate(lines):
        if line == "\n":
            lines_group += 1

        if lines_group == 3 and not inserted_target_arch:
            lines.insert(i, poison_target_arch)
            inserted_target_arch = True

        if lines_group == 10 and not inserted_config_arch_dis:
            lines.insert(i, poison_config_arch_dis)
            inserted_config_arch_dis = True

        if inserted_target_arch and inserted_config_arch_dis:
            break

    with open(poison_header, "w") as f:
        f.write("".join(lines))


class CPUInfo(object):
    "This class store CPU info which editing does not support by the GUI."

    def __init__(self,
        registers = None,
        pc_register = "pc",
        name_to_format = None,
        instructions = None,
        read_size = 1,
        reg_types = None
    ):
        """
    :param registers:
        list of `CPURegister`s used in CPU

    :param pc_register:
        the name of one of the registers specified above that will be
        considered a program counter

    :param name_to_format:
        dictionary which describes operand formatting rules for disassembler

    :param instructions:
        list of `Instruction`s available in CPU

    :param read_size:
        number of bytes of instruction to be read at one time
        (support 1, 2, 4 or 8 bytes)

    :param reg_types:
        callable object which must register types that can be used in several
    instruction semantics
        """

        self.registers = [] if registers is None else registers
        self.pc_register = pc_register
        self.name_to_format = {} if name_to_format is None else name_to_format
        self.instructions = [] if instructions is None else instructions
        self.read_size = read_size
        self.reg_types = (lambda : None) if reg_types is None else reg_types
