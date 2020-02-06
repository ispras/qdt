from debug import (
    git_repo_by_dwarf,
    Runtime,
    Watcher,
    InMemoryELFFile,
    GitLineVersionAdapter,
    DWARFInfoCache
)
from argparse import (
    ArgumentParser
)
from common import (
    pypath
)
# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.rsp import (
        AMD64
    )
    from pyrsp.utils import (
        find_free_port,
        wait_for_tcp_port
    )
from subprocess import (
    Popen
)


class RecWatcher(Watcher):

    def on_retrace_initialize(self):
        # end of function
        "retrace.c:156 39d5c8f5191a4f2e56489dc0e1b02c9144b0df56"
        self.ctx = ctx = self.rt["rtc_ctx"]
        self.load_stream = ls = ctx["execution_load_stream"].to_global()
        self.lc = ls["load_counter"].to_global()

    def on_cpu_common_reset(self):
        # remembering address of instruction counter
        "qom/cpu.c:288 39d5c8f5191a4f2e56489dc0e1b02c9144b0df56"
        self.ic = self.ctx["insn_counter"].dereference().to_global()

    def on_retrace_misc_save(self):
        # function entry
        "retrace_misc.c:12 39d5c8f5191a4f2e56489dc0e1b02c9144b0df56"
        print(self.ic.fetch(), self.lc.fetch())


class TCGWatcher(Watcher):

    def on_tcg_context_init(self):
        "tcg/tcg.c:742 v2.12.1"
        ctx = self.rt["s"]
        res = ctx.dereference()
        print(res)

    def on_tcg_register_thread(self):
        "tcg/tcg.c:565 v2.12.1"

        self.tcg_ctx = self.rt["s"].dereference().to_global()

    def on_translate_loop(self):
        "translator.c:127 v2.12.1"

        # tcg_ctx = self.rt["tcg_ctx"].cast("TCGContext")
        # tcg_ctx = self.rt["tcg_init_ctx"] # it's initial value only
        tcg_ctx = self.tcg_ctx
        ops = tcg_ctx["ops"]
        op = ops["tqh_first"]
        while op.fetch_pointer():
            opc = op["opc"]
            param1 = op["param1"]
            param2 = op["param2"]
            life = op["life"]

            print(list(map(lambda v : v.fetch(), (opc, param1, param2, life))))

            # Field access chains memory location expressions.
            # So, convert intermediate value to a global to prevent a deep
            # expressions during handling of a long list.
            op = op["link"]["tqe_next"].to_global()

        print("!")


if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("qarg", nargs = "+")
    args = ap.parse_args()

    qemu_bin = args.qarg[0]
    elf = InMemoryELFFile(qemu_bin)
    di = elf.get_dwarf_info()
    dic = DWARFInfoCache(di,
        symtab = elf.get_section_by_name(".symtab")
    )

    repo = git_repo_by_dwarf(di)
    gvl_adptr = GitLineVersionAdapter(repo)
    w = RecWatcher(dic, line_adapter = gvl_adptr, verbose = True)

    port = find_free_port(1234)
    qemu_debug_addr = "localhost:%u" % port

    qemu_proc = Popen(["gdbserver", qemu_debug_addr] + args.qarg)

    if not wait_for_tcp_port(port):
        raise RuntimeError("gdbserver does not listen %u" % port)

    qemu_debugger = AMD64(str(port), noack = True, verbose = False)

    try:
        rt = Runtime(qemu_debugger, dic)
        w.init_runtime(rt)

        rt.target.run(setpc = False)
    finally:
        qemu_proc.kill()
