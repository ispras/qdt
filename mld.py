from multiprocessing import Process
from os import system
from time import sleep
from debug import (
    Runtime,
    InMemoryELFFile,
    DWARFInfoCache,
    Watcher,
    value
)
from sys import (
    stderr,
    path
)
import typing
from argparse import ArgumentParser

path.insert(0, "pyrsp")

# noinspection PyUnresolvedReferences
from pyrsp.rsp import (
    AMD64
)
# noinspection PyUnresolvedReferences
from pyrsp.utils import (
    find_free_port,
    wait_for_tcp_port
)

ULONG_SIZE = 4


def preload_headers(dic):
    """
    :param dic: DWARFInfoCache
    """
    files = ["translate.c"]
    for f in files:
        cu = dic.get_CU_by_name(f)
        dic.account_line_program_CU(cu)


class RegWatcher(Watcher):
    def __init__(self, dic, verbose=False):
        """
        :param dic: DWARFInfoCache
        """
        preload_headers(dic)
        super(RegWatcher, self).__init__(dic, verbose=verbose)

        self.tcg_ctx = None  # type: value.Value
        self.last_op = None  # type: value.Value
        # maps guest instruction pointer to tcg ops
        self.ir_map = {}  # type: typing.Dict[int, typing.List[str]]

    def get_field(self, obj_name, field_name, size=4):
        obj = self.rt[obj_name]
        obj_ptr = obj.fetch_pointer()
        field_ptr = obj_ptr + obj[field_name].datum.location.refs[1]
        return self.rt.target.get_val(field_ptr, size)

    def fetch_local_var(self, var_name, size=ULONG_SIZE):
        return self.rt[var_name].fetch(size)

    def tcg_next_op_add(self):
        if self.last_op is not None:
            elem = self.last_op
        else:
            ops = self.tcg_ctx["ops"]
            elem = ops["tqh_first"]
        instr_mapping = []  # type: typing.List[str] # type: typing.List[value.Value]
        while elem.fetch(ULONG_SIZE) != 0:
            instr_mapping.append(elem["opc"].enum_name)
            elem = elem["link"]["tqe_next"].to_global()
            self.last_op = elem
        self.ir_map[self.fetch_local_var("pc")] = instr_mapping

    def dump_current_ops(self):
        ops = self.tcg_ctx["ops"]
        elem = ops["tqh_first"]
        while elem.fetch(ULONG_SIZE) != 0:
            opc = elem["opc"]
            param1 = elem["param1"].fetch()
            param2 = elem["param2"].fetch()
            life = elem["life"].fetch()
            print("opc: %s, param1: %d, param2: %d, life: %d" % (opc.enum_name, param1, param2, life))
            elem = elem["link"]["tqe_next"].to_global()

    def dump_regs(self):
        # tgn = self.rt["tcg_target_reg_names"].fetch_pointer()
        # print("tgn: 0x%x", tgn)
        nb_temps = self.tcg_ctx["nb_temps"].fetch(4)
        print("nb_temps: 0x%x" % nb_temps)
        temps = self.tcg_ctx["temps"]

        for i in range(nb_temps):
            val_t = temps[i]["val_type"]
            name = val_t.enum_name
            if name == 'TEMP_VAL_DEAD':
                continue
            print("%d-th has %s type" % (i, name))

    def print_guest_to_tcg(self):
        from pprint import pprint
        pprint(self.ir_map)

    def traverse_list(self):
        ops = self.tcg_ctx["ops"]
        op = ops["tqh_first"]
        # last_op = ops["tqh_last"]
        while op.fetch(ULONG_SIZE) != 0:
            opc = op["opc"]
            op = op["link"]["tqe_next"]

    # ~~ BP Handlers ~~

    def on_tcg_context_init(self):
        "tcg/tcg.c:684 v2.12.0"

        if self.tcg_ctx is not None:
            print("tcg_context_init called multiple times")
            return
        assert self.tcg_ctx is None
        self.tcg_ctx = self.rt["s"].dereference()
        if self.verbose:
            print("fetched tcg_ctx: 0x%x" % self.tcg_ctx.datum.location.eval(self.rt))

    def on_tcg_gen_insn_start(self):
        """
        tcg/tcg-op.h:739 v2.12.0
        """
        # """
        # tcg/tcg-op.h:734 v2.12.0
        # tcg/tcg-op.h:739 v2.12.0
        # tcg/tcg-op.h:746 v2.12.0
        # tcg/tcg-op.h:751 v2.12.0
        # tcg/tcg-op.h:761 v2.12.0
        # tcg/tcg-op.h:767 v2.12.0
        # """

        pc = self.fetch_local_var("pc")
        if self.verbose:
            print("rewritten pc")
        if self.verbose:
            # self.dump_regs()
            # self.dump_current_ops()
            self.tcg_next_op_add()
            print("on_tcg_gen_insn_start, pc at 0x%x" % pc)

    def on_entry_point(self):
        "linux-user/main.c:4530"
        print("entry point")

    def on_gen_tb_start(self):
        "exec/gen-icount.h:11 v2.12.0"

        self.ir_map = {}

        if self.verbose:
            print("on_gen_tb_start insns")

    def on_gen_tb_end(self):
        "exec/gen-icount.h:56 v2.12.0"

        if self.verbose:
            print("on_gen_tb_end insns in block: 0x%x", self.fetch_local_var("num_insns"))
            self.print_guest_to_tcg()

    def on_finish(self):
        "linux-user/main.c:5147 v2.12.0"

        if self.verbose:
            print('On finish')
        exit(0)


def main():
    ap = ArgumentParser(
        description="QEMU runtime introspection tool"
    )
    ap.add_argument("qarg",
                    nargs="+",
                    help="QEMU executable and arguments to it. Prefix them with `--`."
                    )
    args = ap.parse_args()

    # executable
    qemu_cmd_args = args.qarg

    # debug info
    qemu_debug = qemu_cmd_args[0]

    elf = InMemoryELFFile(qemu_debug)
    if not elf.has_dwarf_info():
        stderr("%s does not have DWARF info. Provide a debug QEMU build\n" % (
            qemu_debug
        ))
        return -1

    di = elf.get_dwarf_info()

    if not di.debug_pubnames_sec:
        print("%s does not contain .debug_pubtypes section. Provide"
              " -gpubnames flag to the compiler" % qemu_debug
              )
    dic = DWARFInfoCache(di,
                         symtab=elf.get_section_by_name(b".symtab")
                         )

    rwtr = RegWatcher(dic, verbose=True)

    # auto select free port for gdb-server
    port = find_free_port()

    qemu_debug_addr = "localhost:%u" % port

    qemu_proc = Process(
        target=system,
        # XXX: if there are spaces in arguments this code will not work.
        args=(" ".join(["gdbserver", "--disable-randomization", qemu_debug_addr] + qemu_cmd_args),)
    )

    qemu_proc.start()

    sleep(1)
    if not wait_for_tcp_port(port):
        raise RuntimeError("gdbserver does not listen %u" % port)

    qemu_debugger = AMD64(str(port), noack=True)

    rt = Runtime(qemu_debugger, dic)

    rwtr.init_runtime(rt)

    rt.target.run(setpc=False)

    rt.target.exit = True
    if qemu_proc is not None:
        qemu_proc.join()


if __name__ == "__main__":
    main()
