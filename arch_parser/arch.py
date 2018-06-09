__all__ = [
      "Arch"
]

from importlib import (
    import_module
)
from os import (
    makedirs
)
from os.path import (
    sep,
    exists,
    join,
    isfile,
)
from qemu import (
    get_vp
)
from .arch_gen import (
    TargetCodeGenerator
)
from .instruction import (
    BYTE_SIZE,
    InstructionNode,
    find_common_opcode
)
from source import (
    Header,
    Source,
    Type,
    Function,
    Structure,
    Pointer,
    Macro,
    Initializer,
    Variable,
    Enumeration
)
from re import (
    compile
)

NECESSARY_FILES = [
    'cpu.h', 'translate.inc.c', 'cpu.c', 'helper.c', 'machine.c', 'translate.c'
]

class GenFile(object):
    def __init__(self,
                 name,
                 base_folder,
                 root,
                 open = False,
                 overwrite = False
        ):
        self.name = name
        self.path = join(base_folder, name)
        self.abs_path = join(root, self.path)
        self.base_folder = base_folder
        self.fd = None
        self.is_header = name[-1] == 'h' or name.find('.inc.c') != -1
        if self.is_header:
            f = Header(self.path)
        else:
            f = Source(self.path)
        self.f = f
        self.opened = False
        self.overwrite = overwrite
        if open:
            self.open()

    def add_type(self, t):
        self.f.add_type(t)

    def add_inclusion(self, h):
        self.f.add_inclusion(h)

    def add_reference(self, r):
        if not self.is_header:
            raise Exception(
                "Trying to add reference to Source file %s" % self.path
            )
        self.f.add_reference(r)

    def add_global_variable(self, var):
        self.f.add_global_variable(var)

    def add_usage(self, usage):
        self.f.add_usage(usage)

    def open(self, mode = 'w'):
        self.opened = True

        if isfile(self.abs_path):
            if self.overwrite:
                print('Existing file %s is overwritten' % self.path)
                ow = 'y'
            else:
                print('File exists %s' % self.path)
                ow = input('Do you want to overwrite it?[yN] ')
            if ow == 'y':
                self.fd = open(self.abs_path, 'w')
            else:
                self.opened = False
        else:
            self.fd = open(self.abs_path, mode)

    def generate(self):
        if self.opened:
            self.f.generate().generate(self.fd)

    def close(self):
        if self.opened:
            self.fd.close()
        self.opened = False


class Arch(object):
    def __init__(self, name,
                 qemu_root = None,
                 arch_bigendian = False,
                 verbose = False,
                 debug_decoder = False,
                 overwrite = False):

        if name is None:
            raise Exception('arch name isn\'t provided')
        self.name = name
        self.target_cpu = None
        self.instructions = []
        self.name_to_format = {}

        self.overwrite = overwrite

        self.instr_size_is_fixed = False
        self.fixed_size = 0
        self.min_size = 0
        self.max_size = 0

        # instruction parsing tree root
        self.instr_tree_root = None

        self.qemu_root = qemu_root
        self.target_folder = get_vp("target folder") + name + sep

        abs_target_folder = join(qemu_root, self.target_folder)
        if not exists(abs_target_folder):
            makedirs(abs_target_folder)

        self.gen_files = {
            fl.name: fl for fl in [
                GenFile(
                    f,
                    self.target_folder,
                    self.qemu_root, True,
                    overwrite = overwrite
                ) for f in NECESSARY_FILES
            ]
        }

        self.arch_bigendian = arch_bigendian
        self.desc_bigendian = False
        self.byte_swap = not self.arch_bigendian
        self.read_size = 1

        self.debug_decoder = debug_decoder
        self.verbose_gen = verbose

        self.content_parser = None

        self.g = None

    def fill(self, ilist = None, cpu = None):
        if ilist is None:
            instr_module = import_module(
                name = 'arch_desc.instruction_list_' + self.name
            )
            self.instructions = instr_module.instruction_list

            try:
                self.name_to_format = instr_module.name_to_format
            except AttributeError:
                pass

            try:
                self.desc_bigendian = instr_module.desc_bigendian
            except AttributeError:
                pass

            try:
                self.read_size = instr_module.read_size
            except AttributeError:
                pass

            self.byte_swap = self.desc_bigendian == self.arch_bigendian
        else:
            print('Arch.fill: ilist is provided')
            self.instructions = ilist

        print('ISA descirption is provided in %s-endian' %
              ('big' if self.desc_bigendian else 'little'))

        tmp = []
        for i in self.instructions:
            tmp.extend(i.expand(self.read_size * BYTE_SIZE))

        self.instructions = tmp

        if cpu is None:
            cpu_module = import_module(name = 'arch_desc.cpu_' + self.name)
            self.target_cpu = cpu_module.target_cpu
        else:
            print('Fill: target_cpu is provided')
            self.target_cpu = cpu

        self.instr_size_is_fixed = \
            len(set([len(instr) for instr in self.instructions])) == 1
        self.fixed_size = len(self.instructions[0])

        self.min_size = min([len(instr) for instr in self.instructions])
        self.max_size = max([len(instr) for instr in self.instructions])
        if self.instr_size_is_fixed:
            print(
'{} is a {}-endian fixed instruction size architecture with size = {}'.format(
                self.name.upper(),
                'big' if self.arch_bigendian else 'little',
                self.fixed_size)
            )
        else:
            print('%s is a %s-endian variable instruction size '
                  'architecture with min_size = %d and max_size = %d'
                  % (self.name.upper(),
                     'big' if self.arch_bigendian else 'little',
                     self.min_size,
                     self.max_size))

        # maybe should correct opc index (e.g. common opcode is in the middle,
        # but some instructions have common parts before
        def build_instruction_tree(cur_node,
                                   instructions,
                                   depth,
                                   prev_instructions = []
            ):
            if instructions == prev_instructions:
                raise Exception('Recursion error')
            orig_opc = find_common_opcode(instructions)
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
                cur_node.instruction = unique.pop()

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
                if self.verbose_gen:
                    print('Instructions conflict found')
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
                            if self.verbose_gen:
                                print('Conflict resolved')
                            break
                        offset += length
                    if not conflict:
                        break
            if conflict:
                if self.verbose_gen:
                    print('FAIL: conflict for ops:')
                    for instr in instructions:
                        instr.dump(verbose = True)
                comm0 = instructions[0].comment
                name0 = instructions[0].name
                comm1 = instructions[1].comment
                name1 = instructions[1].name
                raise Exception(
                    'Unresolved conflict: "' +
                    (comm0 if comm0 != '' else name0) +
                    '" with "' +
                    (comm1 if comm1 != '' else name1) + '"'
                )

            tmp_dict = {}
            for ins in instructions:
                key = ins.get_opcode_part(opc)
                if key is None or len(key) != opc[1]:
                    key = 'default'
                if key not in tmp_dict.keys():
                    tmp_dict[key] = [ins]
                else:
                    tmp_dict[key].append(ins)
            for key, instrs in tmp_dict.items():
                cur_node.opc_dict[key] = InstructionNode()
                build_instruction_tree(
                    cur_node.opc_dict[key],
                    instrs,
                    depth + 1,
                    instructions
                )

            return cur_node

        self.instr_tree_root = build_instruction_tree(
            self.instr_tree_root,
            self.instructions,
            0
        )

        # now we can correctly init self.g
        self.g = TargetCodeGenerator(self)

        return 0

    def gen_target_code(self):
        f = open(
            join(
                self.qemu_root, 'default-configs', self.name + '-softmmu.mak'
            ),
            'w'
        )
        f.write('# Default configuration for ' + self.name + '-softmmu')
        f.close()

        def gen_arch_config():
            def update_configure():
                f = open(join(self.qemu_root, 'configure'), "r")
                lines = f.readlines()
                f.close()

                insert_be = not self.arch_bigendian
                insert_target = False
                insert_disas_config = False
                find_target_abi_dir = False
                find_disas_config = False
                for i, line in enumerate(lines):
                    if line == 'TARGET_ABI_DIR=""\n':
                        find_target_abi_dir = True
                    if find_target_abi_dir and not insert_target:
                        if lines[i] == '  ' + self.name + ')\n':
                            return
                        if lines[i] == '  *)\n':
                            lines.insert(
                                i,
                                '  ' + self.name + ')\n'
                            )
                            lines.insert(
                                i + 1,
                                '    TARGET_ARCH=' + self.name + '\n'
                            )
                            lines.insert(
                                i + 2,
                                '    TARGET_BASE_ARCH=' + self.name + '\n'
                            )
                            lines.insert(
                                i + 3,
                                '  ;;\n'
                            )
                            insert_target = True

                    if line == 'disas_config() {\n':
                        find_disas_config = True
                    if find_disas_config and not insert_disas_config:
                        if line == '  ' + self.name + ')\n':
                            return
                        if line == '  esac\n':
                            lines.insert(
                                i,
                                '  ' + self.name + ')\n'
                            )
                            lines.insert(
                                i + 1,
                                '    disas_config "' + self.name.upper() + '"\n'
                            )
                            lines.insert(
                                i + 2,
                                '  ;;\n'
                            )
                            insert_disas_config = True

                    if not insert_be and lines[i] == 'target_bigendian="no"\n':
                        if lines[i + 3].find(self.name + '|') != -1:
                            return
                        lines[i + 3] = '  ' + \
                            self.name + '|' + \
                            lines[i + 3].lstrip()
                        insert_be = True

                    if insert_be and insert_target and insert_disas_config:
                        break

                f = open(join(self.qemu_root, 'configure'), "w")
                lines = "".join(lines)
                f.write(lines)
                f.close()

            def update_archinit():
                arch_init_header = join(
                    self.qemu_root, 'include', 'sysemu', 'arch_init.h'
                )
                f = open(arch_init_header, 'r')
                lines = f.readlines()
                f.close()

                offset = -2
                str_qemu_arch = '    QEMU_ARCH_' + self.name.upper()
                for i, line in enumerate(lines):
                    if line == '    QEMU_ARCH_ALL = -1,\n':
                        offset = -1

                    if offset != -2:
                        if str_qemu_arch in line:
                            break
                        elif 'QEMU_ARCH_' in line:
                            offset += 1
                        elif line == '};\n':
                            lines.insert(
                                i,
                                str_qemu_arch + ' = (1 << ' + str(offset) + '),\n'
                            )
                            break

                f = open(arch_init_header, "w")
                lines = "".join(lines)
                f.write(lines)
                f.close()

                arch_init_source = join(self.qemu_root, 'arch_init.c')
                f = open(arch_init_source, 'r')
                lines = f.readlines()
                f.close()

                str_target = 'TARGET_' + self.name.upper()
                for i, line in enumerate(lines):
                    if str_target in line:
                        return

                    if line == '#endif\n' and \
                        '#define QEMU_ARCH QEMU_ARCH_' in lines[i - 1]:
                        lines.insert(
                            i,
                            '#elif defined(' + str_target + ')\n'
                        )
                        lines.insert(
                            i + 1,
                            '#define QEMU_ARCH QEMU_ARCH_' + self.name.upper() + '\n'
                        )
                        break

                f = open(arch_init_source, "w")
                lines = "".join(lines)
                f.write(lines)
                f.close()

            def update_bfd():
                bfd_header = join(self.qemu_root, 'include', 'disas', 'bfd.h')
                f = open(bfd_header, 'r')
                lines = f.readlines()
                f.close()

                bfd_arch = '  bfd_arch_' + self.name + ',\n'
                for i, line in enumerate(lines):
                    if line == bfd_arch:
                        break
                    elif line == '  bfd_arch_last\n':
                        lines.insert(i, bfd_arch)
                        break

                decl_func = 'int print_insn_' + self.name + "(bfd_vma, disassemble_info*);\n"
                to_print = False
                for i, line in enumerate(lines):
                    if 'print_insn_' in line:
                        to_print = True
                        if line == decl_func:
                            break
                    elif to_print:
                        lines.insert(
                            i,
                            decl_func
                        )
                        break;

                f = open(bfd_header, "w")
                lines = "".join(lines)
                f.write(lines)
                f.close()

            update_configure()
            update_archinit()
            update_bfd()
            return 0

        # here mkdir target-$(ARCH_NAME) and gen all necessary files
        def gen_target_files():
            hdr = self.gen_files['cpu.h']

            exec_c = Source("exec.c")
            exec_c.add_reference(Type.lookup("TARGET_PAGE_SIZE"))
            exec_c.add_inclusion(hdr.f)

            cpu_arch_state = self.target_cpu.gen_state()
            hdr.add_type(cpu_arch_state)

            state_macro = Macro(
                'CPUArchState',
                text = 'struct CPU' + self.name.upper() + 'State'
            )
            hdr.add_type(state_macro)
            Header.lookup("tcg.h").add_reference(state_macro)
            Header.lookup("exec/cpu-all.h").add_reference(state_macro)
            Header.lookup(
                "exec/cpu-all.h"
            ).add_reference(Type.lookup('TARGET_LONG_SIZE'))

            target_defines = [
                'TARGET_LONG_BITS', 'TARGET_PAGE_BITS',
                'TARGET_PHYS_ADDR_SPACE_BITS',
                'TARGET_VIRT_ADDR_SPACE_BITS',
                'NB_MMU_MODES'
            ]

            for define_name in target_defines:
                m = Macro(
                    define_name,
                    text = self.target_cpu.get_attribute_val(define_name)
                )

                hdr.add_type(m)
                if define_name in ['TARGET_LONG_BITS', 'NB_MMU_MODES']:
                    Header.lookup("exec/cpu-defs.h").add_reference(m)

            arch_cpu = Structure(self.name.upper() + 'CPU')
            arch_cpu.append_field_t_s('CPUState', 'parent_obj')
            arch_cpu.append_field_t_s(
                self.target_cpu.get_cpustate_name(),
                'env'
            )
            hdr.add_type(arch_cpu)

            arch_cpu = Macro(
                'TYPE_' + self.name.upper() + '_CPU',
                text = '\"' + self.name + '-cpu\"'
            )
            hdr.add_type(arch_cpu)

            hdr.add_type(
                Macro(
                    'cpu_init',
                    args = ['cpu_model'],
                    text = 'CPU(cpu_' + self.name + '_init(cpu_model))'
                )
            )

            enum = Enumeration(
                'excp_enum',
                {
                    'EXCP_ILLEGAL': 1
                }
            )
            hdr.add_type(enum)

            handle_mmu_fault = Function(
                self.name + '_cpu_handle_mmu_fault',
                ret_type = Type.lookup('int'),
                args = [
                    Type.lookup('CPUState').gen_var('cs', pointer = True),
                    Type.lookup('vaddr').gen_var('address'),
                    Type.lookup('int').gen_var('rw'),
                    Type.lookup('int').gen_var('mmu_idx')
                ],
                body = 'return 0;\n'
            )
            hdr.add_type(handle_mmu_fault)

            m_get_cpu = Macro(
                'ENV_GET_CPU',
                ['e'],
                'CPU(' + self.name + '_env_get_cpu(e))'
            )
            hdr.add_type(m_get_cpu)

            m_env_offset = Macro(
                'ENV_OFFSET',
                text = 'offsetof(' + self.name.upper() + 'CPU' + ', env)'
            )
            hdr.add_type(m_env_offset)

            env_get_cpu = Function(
                self.name + '_env_get_cpu',
                ret_type = Pointer(
                    Type.lookup(self.target_cpu.get_cpu_name())
                ),
                static = True, inline = True,
                args = [
                    Type.lookup(
                        self.target_cpu.get_cpustate_name()
                    ).gen_var('env', pointer = True)
                ]
            )
            self.g.gen_env_get_cpu(env_get_cpu)
            hdr.add_type(env_get_cpu)

            cpu_mmu_index = Function(
                'cpu_mmu_index',
                ret_type = Type.lookup('int'),
                static = True,
                inline = True,
                args = [
                    Type.lookup(
                        self.target_cpu.get_cpustate_name()
                    ).gen_var('env', pointer = True),
                    Type.lookup('bool').gen_var('ifetch')
                ]
            )
            self.g.gen_cpu_mmu_index(cpu_mmu_index)
            hdr.add_type(cpu_mmu_index)

            get_tb_cpu_state = Function(
                'cpu_get_tb_cpu_state',
                static = True,
                inline = True,
                args = [
                    Type.lookup(
                        self.target_cpu.get_cpustate_name()
                    ).gen_var('env', pointer = True),
                    Type.lookup(
                        'target_ulong'
                    ).gen_var('pc', pointer = True),
                    Type.lookup(
                        'target_ulong'
                    ).gen_var('cs_base', pointer = True),
                    Type.lookup(
                        'uint32_t'
                    ).gen_var('flags', pointer = True)
                ]
            )
            self.g.gen_cpu_get_tb_cpu_state(get_tb_cpu_state)
            hdr.add_type(get_tb_cpu_state)

            hdr.add_inclusion(Header.lookup('exec/cpu-all.h'))
            hdr.add_reference(Type.lookup('MIN'))
            Header.lookup(
                'exec/exec-all.h'
            ).add_reference(Type.lookup('CPUArchState'))

            cpu_class = Macro(
                self.name.upper() + '_CPU_CLASS', args = ['klass'],
                text = 'OBJECT_CLASS_CHECK(' + self.name.upper()
                    + 'CPUClass, (klass), '
                    + arch_cpu.name + ')'
            )
            hdr.add_type(cpu_class)

            cpu = Macro(
                self.name.upper() + '_CPU',
                args = ['obj'],
                text = 'OBJECT_CHECK(' + self.name.upper()
                     + 'CPU, (obj), TYPE_'
                     + self.name.upper() + '_CPU)'
            )

            hdr.add_type(cpu)

            get_class = Macro(
                self.name.upper() + '_CPU_GET_CLASS',
                args = ['obj'],
                text = 'OBJECT_GET_CLASS(' + self.name.upper()
                    + 'CPUClass, (obj), TYPE_'
                    + self.target_cpu.get_cpu_name() + ')'
            )

            hdr.add_type(get_class)

            cpu_class = Structure(self.name.upper() + 'CPUClass')
            cpu_class.append_field_t_s('CPUClass', 'parent_class')
            cpu_class.append_field_t_s('DeviceRealize', 'parent_realize')
            field_func = Function('parent_reset', args = [
                Type.lookup('CPUState').gen_var('cpu', pointer = True)
            ])
            pfunc = Pointer(field_func, 'DeviceReset')
            cpu_class.append_field(pfunc.gen_var('parent_reset'))
            cpu_class.append_field_t_s('uint32_t', 'vr')
            hdr.add_type(cpu_class)

            helper_c = self.gen_files['helper.c']

            tlb_fill = Type.lookup('tlb_fill').gen_body()
            self.g.gen_tlb_fill(tlb_fill)
            handle_mmu_fault_body = handle_mmu_fault.gen_body()
            self.g.gen_handle_mmu_fault(handle_mmu_fault_body)

            helper_c.add_type(handle_mmu_fault_body)
            helper_c.add_type(tlb_fill)

        def gen_instruction_funcs_file():
            h = self.gen_files['translate.inc.c']

            disas_context = Structure('DisasContext')
            disas_context.append_field_t_s(
                'TranslationBlock', 'tb',
                pointer = True
            )
            disas_context.append_field_t_s('uint64_t', 'pc')
            disas_context.append_field_t_s('uint64_t', 'opcode')
            disas_context.append_field_t_s('int', 'bstate')
            disas_context.append_field_t_s('bool', 'singlestep_enabled')
            h.add_type(disas_context)

            Header.lookup('exec/cpu_ldst.h').add_reference(disas_context)

        def gen_vmstate_desc():
            src = self.gen_files['machine.c']

            field_str = ''
            indent = ' ' * 8

            for field in self.target_cpu.fields:
                fstr = 'VMSTATE_' + field.type.rstrip('_t').upper()
                fdict = {
                    '_f': field.name,
                    '_s': 'CPU' + self.name.upper() + 'State'
                }
                if field.num is not None:
                    fstr += '_ARRAY'
                    fdict.update(
                        {'_n': str(field.num)} if field.num is not None else {}
                    )
                field_str += Type.lookup(
                    fstr
                ).gen_usage_string(Initializer(fdict)) + ',\n' + indent

            field_str += "VMSTATE_END_OF_LIST()"

            vmstate = Variable(
                'vmstate_' + self.name + '_cpu',
                Type.lookup('VMStateDescription'),
                const = True,
                initializer = Initializer(
                    code =
"""{{
    .name = \"{name}\",
    .version_id = {id},
    .minimum_version_id = {min_id},
    .fields = (VMStateField[]) {{
        {field_str}
    }}
}}""".format(name = "cpu", id = 1, min_id = 1, field_str = field_str),
                    used_types = [
                        Type.lookup(self.target_cpu.get_cpustate_name())
                    ]
                )
            )
            src.add_global_variable(vmstate)

        def gen_makefile():
            mkf = open(
                join(self.qemu_root, self.target_folder, 'Makefile.objs'),
                'w'
            )
            mkf.write('obj-y +=')
            for obj in NECESSARY_FILES:
                if obj[-1] == 'c' and obj.find('.inc.c') == -1:
                    mkf.write(' ' + obj[:-2] + '.o')
            mkf.write('\n')
            mkf.close()

        def gen_helper():
            h = open(join(self.qemu_root, self.target_folder, 'helper.h'), 'w')
            h.write('DEF_HELPER_1(debug, void, env)\n')
            h.write('DEF_HELPER_1(illegal, void, env)\n')
            h.close

        def gen_translation_code():
            src = self.gen_files['translate.c']

            enum = Enumeration(
                'br_enum',
                {
                    'BS_NONE': 0,
                    'BS_STOP': 1,
                    'BS_BRANCH': 2,
                    'BS_EXCP': 3
                }
            )
            src.add_type(enum)

            decode_opc = Function(
                 'decode_opc',
                 ret_type = Type.lookup('int'),
                 args = [
                    Type.lookup(self.name.upper() + 'CPU').gen_var(
                        'cpu',
                        pointer = True
                    ),
                    Type.lookup('DisasContext').gen_var('ctx', pointer = True)
                ],
                static = True
            )

            self.g.gen_decode_opc(
                decode_opc,
                src.f.global_variables['cpu_pc'],
                src.f.global_variables['cpu_env']
            )
            decode_used_types = [Type.lookup(instr.name)
                              for instr in self.instructions]
            decode_used_types.extend(
                [
                    Type.lookup('uint32_t'),
                    Function.lookup('cpu_ldl_code'),
                    Function.lookup('printf')
                ]
            )
            decode_opc.used_types = decode_used_types
            src.add_type(decode_opc)

            gic_used_types = [
                Type.lookup('uint32_t'),
                decode_opc,
                Function.lookup('gen_intermediate_code'),
                Type.lookup('DisasContext'),
                Function.lookup('gen_tb_start'),
                Type.lookup('log_target_disas'),
                Type.lookup('qemu_log'),
                Type.lookup('lookup_symbol'),
                Type.lookup('br_enum')
            ]

            if get_vp()['gen_intermediate_code arg1 is generic']:
                arg1 = Type.lookup(
                            'CPUState'
                       ).gen_var('cs', pointer = True)
            else:
                arg1 = Type.lookup(
                            self.target_cpu.get_cpustate_name()
                       ).gen_var('env', pointer = True),
            gen_int_code = Function(
                'gen_intermediate_code.body',
                args = [
                    arg1,
                    Type.lookup(
                        'TranslationBlock'
                    ).gen_var('tb', pointer = True)
                ],
                used_types = gic_used_types
            )
            self.g.gen_gen_intermediate_code(
                gen_int_code,
                src.f.global_variables['cpu_pc'],
                src.f.global_variables['cpu_env']
            )
            src.add_type(gen_int_code)

            restore_state = Function(
                'restore_state_to_opc',
                args = [
                    Type.lookup(
                        self.target_cpu.get_cpustate_name()
                    ).gen_var('env', pointer = True),
                    Type.lookup(
                        'TranslationBlock'
                    ).gen_var('tb', pointer = True),
                    Type.lookup(
                        'target_ulong'
                    ).gen_var('data', pointer = True)
                 ],
                 used_types = []
            )
            self.g.gen_restore_state_to_opc(restore_state)
            src.add_type(restore_state)

        def gen_qom_code():
            self.target_cpu.gen_qom_model(self.gen_files,
                                          self.g)

        gen_arch_config()
        gen_target_files()
        gen_instruction_funcs_file()
        gen_vmstate_desc()
        gen_makefile()
        gen_qom_code()
        gen_translation_code()
        gen_helper()

    def gen_disas(self):
        disas_folder = 'disas'

        def update_makefile():
            makefile = join(self.qemu_root, disas_folder, 'Makefile.objs')
            f = open(makefile, 'r')
            lines = f.readlines()
            f.close()

            config_dis = 'common-obj-$(CONFIG_' + \
                         self.name.upper() + '_DIS) += ' + self.name + '.o\n'
            for line in lines:
                if line == config_dis:
                    return

            lines.insert(len(lines), config_dis)

            f = open(makefile, "w")
            lines = "".join(lines)
            f.write(lines)
            f.close()

        def gen_disas_code():
            df = GenFile(
                self.name + '.c',
                disas_folder,
                self.qemu_root,
                True,
                self.overwrite
            )

            ftr = {
                '%s': 'const char',
                '%d': 'int',
                '%x': 'unsigned',
                '%c': 'char'
            }

            added = {}
            disas_used_types = []

            regs_var = []
            for r in self.target_cpu.reg_groups:
                init_code = '{\n'
                for r1 in r.regs:
                    init_code += '    "' + r1.name + '",\n'
                init_code += '}'
                reg_var = Type.lookup(
                    'const char'
                ).gen_var(
                    r.name,
                    pointer = True,
                    initializer = Initializer(code = init_code),
                    static = True,
                    array_size = len(r),
                    unused = True
                )

                df.add_global_variable(reg_var)
                regs_var.append(reg_var)

            re_spec = compile('(%(?:' +
                '(?:[-+ #0]{0,5})' +       # flags
                '(?:\d+|\*)?' +            # width
                '(?:\.(?:\d+|\*))?' +      # precision
                '(?:hh|h|l|ll|j|z|t|L)?' + # length
                '[diuoxXfFeEgGaAcspn%]))'  # specifier
            )
            for n, v in self.name_to_format.items():
                arg_count = n.count(',') + 1
                if v[1] is not None:
                    if added.get(v[1]) is None:
                        args = [Type.lookup('uint64_t').gen_var('arg' + str(i))
                                for i in range(0, arg_count)
                        ]
                        if v[0] is not None:
                            spec_m = re_spec.search(v[0])
                            if spec_m:
                                specifier = spec_m.group(0)
                            else:
                                specifier = ''
                            if specifier == '%s':
                                ret_type = Pointer(Type.lookup(ftr[specifier]))
                            else:
                                ret_type = Type.lookup(ftr[specifier])
                        else:
                            args.insert(
                                0,
                                Type.lookup('void'
                                ).gen_var('stream', pointer = True)
                            )
                            args.insert(
                                0,
                                Type.lookup('fprintf_function').gen_var('fpr')
                            )
                            ret_type = Type.lookup('void')
                        f = Function(
                            v[1],
                            ret_type = ret_type,
                            args = args,
                            static = True,
                            used_types = regs_var
                        )
                        if v[0] is not None:
                            self.g.gen_helper_disas_write(f)
                        df.add_type(f)
                        disas_used_types.append(f)
                        added[v[1]] = (arg_count, v[0] is None)
                    elif added[v[1]] != (arg_count, v[0] is None):
                        def xstr(a):
                            if a is None:
                                return 'None'
                            else:
                                return '"' + a + '"'
                        raise Exception(
                            '"%s": (%s, "%s") try to use function with '
                            'another number of arguments or argument type than '
                            'before' % (n, xstr(v[0]), v[1])
                        )

            disas_decl = Function('print_insn_' + self.name,
                ret_type = Type.lookup('int'),
                args = [
                    Type.lookup('bfd_vma').gen_var('addr'),
                    Type.lookup('disassemble_info').
                        gen_var('info', pointer = True
                    )
                ]
            )

            Header.lookup(join('disas', 'bfd.h')).add_type(disas_decl)

            disas_def = disas_decl.gen_body(used_types = disas_used_types)
            self.g.gen_print_ins(disas_def)

            df.add_type(disas_def)
            df.generate()
            df.close()

        update_makefile()
        gen_disas_code()


    def gen_all(self):
        self.gen_disas()

        # TODO: add return value check
        self.gen_target_code()
        for f in self.gen_files.values():
            f.generate()
            f.close()
