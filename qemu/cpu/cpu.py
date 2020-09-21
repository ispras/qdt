__all__ = [
    "CPUType"
]

from ..makefile_patching import (
    patch_makefile,
)
from ..qom import (
    QOMCPU,
)
from ..qom_desc import (
    describable,
)
from ..version import (
    get_vp,
)
from .code_generation import *
from .constants import (
    BYTE_BITSIZE,
    SUPPORTED_READ_BITSIZES,
)
from .info import (
    CPUInfo,
)
from .instruction import (
    InstructionTreeNode,
    build_instruction_tree,
)
from codecs import (
    open,
)
from collections import (
    OrderedDict,
    defaultdict,
)
from common import (
    execfile,
    mlget as _,
)
from itertools import (
    count,
)
from os import (
    makedirs,
    remove,
    rename,
)
from os.path import (
    basename,
    isdir,
    isfile,
    join,
    sep,
    splitext,
)
from re import (
    compile,
)
from source import (
    Enumeration,
    Function,
    Header,
    Initializer,
    Macro,
    Pointer,
    Source,
    Structure,
    Type,
    TypeAlias,
    BodyTree,
    OpIndex,
)
from traceback import (
    print_exc,
)
from types import (
    FunctionType,
)


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


def fill_tree_reading_seq(node, read_bitsize, already_read = 0):
    ins = node.instruction
    limit_read = node.limit_read
    del node.limit_read

    if ins:
        node.reading_seq = calc_node_reading_seq(ins.bitsize, already_read,
            limit_read
        )
    else:
        bitoffset, bitsize = node.interval

        reading_seq = calc_node_reading_seq(bitoffset + bitsize, already_read,
            limit_read
        )

        if reading_seq:
            node.reading_seq = reading_seq
            already_read = reading_seq[-1][0] + reading_seq[-1][1]

        for subnode in node.subtree.values():
            fill_tree_reading_seq(subnode, read_bitsize, already_read)


def calc_node_reading_seq(need_read, already_read, limit_read):
    if need_read <= already_read:
        return []

    result = []

    for r_bitsize in SUPPORTED_READ_BITSIZES:
        while (    need_read > already_read
               and already_read + r_bitsize <= limit_read
        ):
            result.append((already_read, r_bitsize))
            already_read += r_bitsize

    return result


def add_global_array_with_reg_names(reg, arr_name, f):
    names_array = Pointer(Type["const char"])(arr_name,
        initializer = Initializer(
            # TODO: `Initializer` should support iterables as `code` for arrays
            code = '{\n    "%s"\n}' % (
                '",\n    "'.join(reg.reg_names)
            )
        ),
        static = True,
        array_size = reg.bank_size
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
            "short": _("Target long size in bits"),
            "input": int
        }),
        ("target_page_bits", {
            "short": _("Log2 of target page size in bytes"),
            "input": int
        }),
        ("target_phys_addr_space_bits", {
            "short": _("Log2 of target physical address space size in bytes"),
            "input": int
        }),
        ("target_virt_addr_space_bits", {
            "short": _("Log2 of target virtual address space size in bytes"),
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
        intermediate_chunk_graphs = False,
        with_debug_comments = False,
        include_paths = tuple(),
        **_
    ):
        import cpu_imports
        loaded = dict(cpu_imports.__dict__)
        try:
            # TODO: use `QProject.lookup_path`
            execfile(self.info_path, loaded)
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

        self.registers = registers = info.registers
        self.pc_register = info.pc_register

        for reg in registers:
            self.add_state_field_h("uint%d_t" % (reg.field_bitsize),
                reg.name,
                num = reg.bank_size,
                save = True
            )

        self.name_to_format = info.name_to_format
        self.instructions = instructions = info.instructions
        self.read_bitsize = read_bitsize = info.read_size * BYTE_BITSIZE
        self.reg_types = info.reg_types
        self.name_shortener = info.name_shortener

        if read_bitsize not in SUPPORTED_READ_BITSIZES:
            raise RuntimeError(
                "Valid `read_size` values are %s bytes" % (", ".join(
                    i // BYTE_BITSIZE for i in SUPPORTED_READ_BITSIZES
                ))
            )

        existing_instruction_names = defaultdict(lambda : count(0))
        for i in instructions:
            i.name = "%s_%d" % (
                i.mnemonic, next(existing_instruction_names[i.mnemonic])
            )
            i.read_bitsize = read_bitsize

        bitsizes = [i.bitsize for i in instructions]
        try:
            min_bitsize = min(bitsizes)
            max_bitsize = max(bitsizes)
        except ValueError:
            min_bitsize = 0
            max_bitsize = 0
        is_fixed_bitsize = min_bitsize == max_bitsize

        self.min_instr_len = min_bitsize

        print("{arch} is a {endianess}-endian {is_fixed} instruction length"
            " architecture with {bitsize_info}".format(
            arch = self.target_name.upper(),
            endianess = "big" if self.target_bigendian else "little",
            is_fixed = "fixed" if is_fixed_bitsize else "variable",
            bitsize_info = (
                "length = %d bits" % min_bitsize if is_fixed_bitsize else
                "minimum length = %d bits and maximum length = %d bits" % (
                    min_bitsize, max_bitsize
                )
            )
        ))

        yield self._co_gen_target_code(src)

        translate_inc_c_file = self.gen_files["translate.inc.c"]
        for f in self.gen_files.values():
            if f is translate_inc_c_file:
                path = join(src, f.path[:-1] + "i3s.c")
            else:
                path = join(src, f.path)

            if intermediate_chunk_graphs:
                graphs_prefix = path + ".chunks"
            else:
                graphs_prefix = None

            with open(path, mode = "wb", encoding = "utf-8") as f_writer:
                sf = f.generate()

                yield True

                sf.generate(f_writer,
                    graphs_prefix = graphs_prefix,
                    gen_debug_comments = with_debug_comments,
                    include_paths = include_paths
                )

                yield True

                if with_chunk_graph:
                    yield True
                    sf.gen_chunks_gv_file(path + ".chunks.gv")

        yield True

        with open(join(src, translate_inc_c_file.path), "w") as f:
            f.write("""\
/* autogenerated temporary translate.inc.c */
#ifndef INCLUDE_TEMPORARY_TRANSLATE_INC_C
#define INCLUDE_TEMPORARY_TRANSLATE_INC_C

#define tcg TCGv
#include "translate.inc.i3s.c"

#endif /* INCLUDE_TEMPORARY_TRANSLATE_INC_C */
""")

    def _co_gen_target_code(self, src):
        if self.instructions:
            read_bitsize = self.read_bitsize
            node = InstructionTreeNode()
            build_instruction_tree(node, self.instructions, read_bitsize)
            fill_tree_reading_seq(node, read_bitsize)
            self.instruction_tree_root = node
        else:
            self.instruction_tree_root = None

        yield True

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

        patch_disas_header(src, self.print_insn_name, self.bfd_arch_name)

        yield True

        patch_poison_header(src, self.target_arch, self.config_arch_dis)

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
            "$(" + self.config_arch_dis + ")"
        )

        yield True

        self._gen_disas(disas)

    def _gen_cpu_param_h(self, h):
        # XXX: lock the header to prevent adding inclusions.
        h.locked_inclusions = True
        # XXX: the "cpu-param.h" header is already included in the
        # "exec/cpu-defs.h" header but on a short path.
        # The tool cannot find such an inclusion yet.
        Header["exec/cpu-defs.h"].add_inclusion(h)

        for name, value in self.attributes.items():
            m = Macro(name, text = value)
            h.add_type(m)

    def _gen_cpu_h(self, h):
        fn_name = self.gen_func_name

        # "cpu.h" header does not require anything from "cpu-all.h" header.
        # "exec.c" source file include "cpu.h" header and require type
        # "TARGET_PAGE_SIZE".
        # Only "cpu.h" header can satisfy the dependency.
        exec_c = Source("exec.c", locked_inclusions = True)
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
        arch_cpu = Structure(self.struct_instance_name, *arch_cpu_fields)
        h.add_type(arch_cpu)

        if get_vp("typedef ArchCPU"):
            arch = TypeAlias(arch_cpu, "ArchCPU")
            h.add_type(arch)
            Header["exec/cpu-all.h"].add_reference(arch)

        if get_vp("typedef CPUArchState"):
            arch_state = TypeAlias(cpu_arch_state, "CPUArchState")
        else:
            arch_state = Macro("CPUArchState",
                text = "struct " + cpu_arch_state.c_name
            )
        h.add_type(arch_state)
        tcg_h = Header[get_vp("tcg headers prefix") + "tcg.h"]
        tcg_h.add_reference(arch_state)
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
                name = self.env_get_cpu_name,
                ret_type = Pointer(arch_cpu),
                args = [ Pointer(cpu_arch_state)("env") ],
                static = True,
                inline = True
            )
            fill_env_get_cpu_body(self, env_get_cpu)
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
        fill_cpu_mmu_index_body(cpu_mmu_index)
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
        fill_cpu_get_tb_cpu_state_body(get_tb_cpu_state, self.pc_register)
        h.add_type(get_tb_cpu_state)

        type_arch_cpu = Macro(self.qtn.type_macro,
            text = '"%s"' % self.qtn.name
        )
        h.add_type(type_arch_cpu)

        cpu_class_fields = [
            Type["CPUClass"]("parent_class"),
            Type["DeviceRealize"]("parent_realize")
        ]
        if get_vp("device_class_set_parent_reset used for cpu"):
            cpu_class_fields.append(Type["DeviceReset"]("parent_reset"))
        else:
            cpu_class_fields.append(
                Function(
                    args = [ Pointer(Type["CPUState"])("cpu") ]
                )("parent_reset")
            )
        cpu_class = Structure(self.struct_class_name, *cpu_class_fields)
        h.add_type(cpu_class)

        class_check = Macro(self.class_macro,
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

        get_class = Macro(self.get_class_macro,
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
                    text = "CPU(%s(cpu_model))" % self.cpu_init_name
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
            Function(name = self.tcg_init_name)
        ])

        if get_vp("cpu_arch_init exists"):
            h.add_type(
                Function(
                    name = self.cpu_init_name,
                    ret_type = Pointer(Type[self.struct_instance_name]),
                    args = [ Pointer(Type["const char"])("cpu_model") ]
                )
            )

    def _gen_translate_inc_c(self, h):
        for reg in self.registers:
            h.add_global_variable(
                Type["tcg"](reg.name, array_size = reg.bank_size)
            )

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
        if isinstance(self.pc_register, tuple):
            reg_name, reg_index = self.pc_register
            pc_register = OpIndex(h.global_variables[reg_name], reg_index)
        else:
            pc_register = h.global_variables[self.pc_register]
        fill_set_pc_inc_body(set_pc, pc_register)

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

        self.reg_types(h)

    def _gen_cpu_c(self, c):
        cpu_class = Type["CPUClass"]
        type_info_type = Type["TypeInfo"]
        fn_name = self.gen_func_name

        if get_vp("device_class_set_parent_reset used for cpu"):
            reset_field = Type["DeviceClass"].reset
        else:
            reset_field = cpu_class.reset
        reset = reset_field.gen_callback(fn_name("reset"), static = True)
        fill_reset_body(self, reset)
        c.add_type(reset)

        disas_set_info = cpu_class.disas_set_info.gen_callback(
            fn_name("disas_set_info"),
            static = True
        )
        fill_disas_set_info_body(self, disas_set_info)
        c.add_type(disas_set_info)

        set_pc = cpu_class.set_pc.gen_callback(fn_name("set_pc"),
            static = True
        )
        fill_set_pc_body(self, set_pc)
        c.add_type(set_pc)

        class_by_name = cpu_class.class_by_name.gen_callback(
            fn_name("class_by_name"),
            static = True
        )
        fill_class_by_name_body(self, class_by_name)
        c.add_type(class_by_name)

        has_work = cpu_class.has_work.gen_callback(
            fn_name("has_work"),
            static = True
        )
        fill_has_work_body(has_work)
        c.add_type(has_work)

        gdb_read_register = cpu_class.gdb_read_register.gen_callback(
            fn_name("gdb_read_register"),
            static = True
        )
        fill_gdb_rw_register_body(self, gdb_read_register)
        c.add_type(gdb_read_register)

        gdb_write_register = cpu_class.gdb_write_register.gen_callback(
            fn_name("gdb_write_register"),
            static = True
        )
        fill_gdb_rw_register_body(self, gdb_write_register, is_write = True)
        c.add_type(gdb_write_register)

        realizefn = Type["DeviceRealize"].type.use_as_prototype(
            fn_name("realizefn"),
            static = True
        )
        fill_realizefn_body(self, realizefn)
        c.add_type(realizefn)

        if get_vp("cpu_arch_init exists"):
            cpu_init_def = Type[self.cpu_init_name].gen_definition()
            fill_cpu_init_body(self, cpu_init_def)
            c.add_type(cpu_init_def)

        cpu_initfn = type_info_type.instance_init.gen_callback(
            fn_name("initfn"),
            static = True
        )
        fill_initfn_body(self, cpu_initfn)
        c.add_type(cpu_initfn)

        cpu_class_init = type_info_type.class_init.gen_callback(
            fn_name("class_init"),
            static = True
        )
        num_core_regs = sum(r.bank_size or 1 for r in self.registers)
        fill_class_init_body(self, cpu_class_init, num_core_regs,
            self.gen_files["cpu.h"].global_variables[
                "vmstate_" + self.qtn.for_id_name
            ]
        )
        c.add_type(cpu_class_init)

        type_info = type_info_type(self.type_info_name,
            initializer = Initializer(
                {
                    "name": Type[self.qtn.type_macro],
                    "parent": Type["TYPE_CPU"],
                    # TODO: support `OpSizeOf` and other related function body
                    #       classes in `Initializer`'s `code`
                    "instance_size": "sizeof(%s)" % self.struct_instance_name,
                    "instance_init": cpu_initfn,
                    "class_size": "sizeof(%s)" % self.struct_class_name,
                    "class_init": cpu_class_init
                },
                used_types = [
                    Type[self.struct_instance_name],
                    Type[self.struct_class_name]
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

    def _gen_helper_c(self, c):
        fn_name = self.gen_func_name

        if get_vp("tlb_fill exists"):
            tlb_fill = Type["tlb_fill"].gen_definition()
            fill_tlb_fill_body(self, tlb_fill)
            c.add_type(tlb_fill)

        if get_vp("CPUClass has tlb_fill field"):
            cpu_tlb_fill = Type[
                fn_name("tlb_fill")
            ].gen_definition()
            fill_cpuclass_tlb_fill_body(cpu_tlb_fill)
            c.add_type(cpu_tlb_fill)
        else:
            handle_mmu_fault = Type[
                fn_name("handle_mmu_fault")
            ].gen_definition()
            fill_handle_mmu_fault_body(handle_mmu_fault)
            c.add_type(handle_mmu_fault)

        raise_exception = self.gen_raise_exception()
        fill_raise_exception_body(self, raise_exception)
        c.add_type(raise_exception)

        helper_debug = self.gen_helper_debug()
        fill_helper_debug_body(helper_debug)
        # avoid warning about missing prototypes
        helper_debug.extra_references = {Type["HELPER_PROTO_H"]}
        c.add_type(helper_debug)

        helper_illegal = self.gen_helper_illegal()
        fill_helper_illegal_body(helper_illegal)
        # avoid warning about missing prototypes
        helper_debug.extra_references = {Type["HELPER_PROTO_H"]}
        c.add_type(helper_illegal)

        Header["exec/helper-gen.h"].add_types([
            helper_debug.use_as_prototype("gen_" + helper_debug.name),
            helper_illegal.use_as_prototype("gen_" + helper_illegal.name)
        ])

        phys_page_debug_def = Type[
            fn_name("get_phys_page_debug")
        ].gen_definition()
        fill_get_phys_page_debug_body(phys_page_debug_def)
        c.add_type(phys_page_debug_def)

        c.add_type(Type[fn_name("do_interrupt")].gen_definition())

    def _gen_machine_c(self, c):
        cpu_arch_state = Type[self.struct_name]
        vmstate = self.gen_vmstate_var(cpu_arch_state)
        c.add_global_variable(vmstate)

    def _gen_translate_c(self, c):
        if get_vp("Init cpu_env in arch"):
            cpu_env = Type["TCGv_env"]("cpu_env", static = True)
            c.add_global_variable(cpu_env)
            Header["exec/gen-icount.h"].add_reference(cpu_env)
        else:
            tcg_h = Header[get_vp("tcg headers prefix") + "tcg.h"]
            cpu_env = tcg_h.global_variables["cpu_env"]

        reg_vars = []
        for reg in self.registers:
            var = Type["TCGv"](reg.name, array_size = reg.bank_size)
            c.add_global_variable(var)

            if reg.bank_size:
                names_array = add_global_array_with_reg_names(
                    reg, reg.name + "_names", c
                )
            else:
                names_array = None

            reg_vars.append((reg, var, names_array))

        cpu_dump_state_def = Type[
            self.gen_func_name("dump_state")
        ].gen_definition()
        fill_dump_state_body(self, cpu_dump_state_def, reg_vars)
        c.add_type(cpu_dump_state_def)

        tcg_init_def = Type[self.tcg_init_name].gen_definition()
        fill_tcg_init_body(self, tcg_init_def, reg_vars, cpu_env)
        c.add_type(tcg_init_def)

        decode_opc = Function(
            name = "decode_opc",
            ret_type = Type["int"],
            args = [
                Pointer(Type[self.struct_instance_name])("cpu"),
                Pointer(Type["DisasContext"])("ctx")
            ],
            static = True
        )
        fill_decode_opc_body(self, decode_opc, cpu_env)
        c.add_type(decode_opc)

        cpu_arch_state_p = Pointer(Type[self.struct_name])

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
        fill_gen_intermediate_code_body(self, gen_int_code_def, cpu_env)
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
        fill_restore_state_to_opc_body(self, restore_state_to_opc)
        c.add_type(restore_state_to_opc)

    def _gen_target_makefile(self, src):
        with open(src, "w") as mkf:
            mkf.write("obj-y +=")

            for f in self.gen_files.values():
                if type(f) is Source:
                    mkf.write(" %s.o" % splitext(basename(f.path))[0])

            mkf.write("\n")

    def _gen_helper_h(self, src):
        with open(src, "w") as h:
            h.write("DEF_HELPER_1(debug, void, env)\n")
            h.write("DEF_HELPER_1(illegal, void, env)\n")

    def _gen_disas(self, c):
        # register own realization of "bfd_getb64"
        fill_bfd_getb64_body(
            Function(
                name = "bfd_getb64",
                ret_type = Type["bfd_vma"],
                args = [ Pointer(Type["const bfd_byte"])("addr") ]
            )
        )

        # TODO: this code is generic enough to be part of `source` module.
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

        reg_names_arrays = set()
        for reg in self.registers:
            if reg.bank_size:
                reg_names_arrays.add(
                    add_global_array_with_reg_names(reg, reg.name, c)
                )

        added = {}
        for op_names, (fmt, adapter) in self.name_to_format.items():
            if adapter is None:
                continue

            if isinstance(adapter, FunctionType):
                adapter_name = adapter.__name__
            else:
                adapter_name = adapter

            arg_count = op_names.count(',') + 1
            if added.get(adapter_name) is None:
                if fmt is not None:
                    f_spec_match = re_format_specifier.search(fmt)
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
                            ' "%s"' % fmt
                        )
                    args = []
                else:
                    args = [
                        Type["fprintf_function"]("fpr"),
                        Pointer(Type["void"])("stream")
                    ]
                    ret_type = Type["void"]

                # TODO: can we derive argument names from `op_names`?
                if arg_count == 1:
                    args += [ Type["uint64_t"]("arg") ]
                else:
                    args += [ Type["uint64_t"]("arg" + str(i))
                        for i in range(0, arg_count)
                    ]

                if isinstance(adapter, FunctionType):
                    f = Function(
                        name = adapter_name,
                        ret_type = ret_type,
                        args = args,
                        static = True
                    )
                    f.body = BodyTree()(*adapter(f, c))
                    # Note, semantics generated by `adapter` must explicitly
                    # reference required `reg_names_arrays`.
                else:
                    f = Function(
                        name = adapter_name,
                        # Note, the user will necessarily write the body of the
                        # function after generation so that it will not be
                        # empty. To simplify the work with git diff, the
                        # brackets will be immediately placed as for a
                        # non-empty function.
                        body = "",
                        ret_type = ret_type,
                        args = args,
                        static = True
                    )

                    # Note, arrays with register names will be used for output
                    # with a high degree of probability. Therefore, they will
                    # immediately be placed above the helper functions.
                    f.extra_references = reg_names_arrays

                    if fmt is not None:
                        fill_disas_write_helper_body(f)

                c.add_type(f)

                added[adapter_name] = (arg_count, fmt is None)
            elif added[adapter_name] != (arg_count, fmt is None):
                raise Exception('"%s": (%r, "%s") try to use function with'
                    " another number of arguments or argument type than"
                    " before" % (op_names, fmt, adapter_name)
                )

        print_insn_def = Type[self.print_insn_name].gen_definition()
        fill_print_insn_body(self, print_insn_def)
        c.add_type(print_insn_def)


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


re_arch_enum_definition = compile("^    (\w+) = \(1 << (\d+)\),\n$")

def patch_arch_init_header(src, target_name):
    arch_init_header = join(src, "include", "sysemu", "arch_init.h")
    target_name_upper = target_name.upper()
    qemu_arch = "QEMU_ARCH_" + target_name_upper

    with open(arch_init_header, "r") as f:
        lines = f.readlines()

    index = 0
    first_enum_found = False
    arch_definitions = {}

    for i, line in enumerate(lines):
        if first_enum_found:
            if line == "};\n":
                index = i
                break
            arch_e_d_match = re_arch_enum_definition.search(line)
            if arch_e_d_match:
                arch_definitions[arch_e_d_match.group(1)] = (
                    int(arch_e_d_match.group(2))
                )
        if line == "enum {\n":
            first_enum_found = True

    if qemu_arch in arch_definitions:
        return

    # Note, QEMU_ARCH_NONE is appeared since Qemu v5.0.0 version. Without using
    # the version heuristic, we just check for the presence in the file.
    QEMU_ARCH_NONE_val = None
    if "QEMU_ARCH_NONE" in arch_definitions:
        # subtracts 2 because QEMU_ARCH_NONE is separated by an empty line
        index = index - 2
        QEMU_ARCH_NONE_val = arch_definitions.pop("QEMU_ARCH_NONE")

    arch_val = max(arch_definitions.values()) + 1

    # Note, each architecture uses its own bit as an enumeration constant,
    # which is of type `int`, therefore the number of architectures is limited
    # by `int` bitsize.
    if arch_val == QEMU_ARCH_NONE_val or arch_val > 31:
        raise RuntimeError("No available bits to declare architecture in " +
            "the 'arch_init' header"
        )

    lines.insert(index, "    %s = (1 << %d),\n" % (qemu_arch, arch_val))

    with open(arch_init_header, "w") as f:
        f.write("".join(lines))


def patch_arch_init_source(src, target_name):
    arch_init_source = join(src, *get_vp("arch_init.c path"))
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

    if i == target_defines_start_idx:
        lines[i] = lines[i][:1] + "el" + lines[i][1:]
        prefix = ""
    else:
        prefix = "el"

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
    r = compile("^int %s *\(bfd_vma, disassemble_info\*\);$" % print_insn_name)
    inserted_print_insn = any(r.match(line) for line in lines)

    if inserted_bfd_arch and inserted_print_insn:
        # Prevent file from being overwritten with the same content
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
