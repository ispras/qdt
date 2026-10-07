#!/usr/bin/env -S python3

""" Qemu Target Test Tool
"""

from common import (
    CLICoDispatcher,
    PortPool,
    pypath,
)
from qemu import (
    print_addr2srclines_map,
    Q3TTestState,
    read_q3t_config,
)

from argparse import (
    ArgumentParser,
)
from os.path import (
    abspath,
    isfile,
    join,
)
from subprocess import (
    PIPE,
    Popen,
)

# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        QMP,
        wait_for_tcp_port,
    )


port_pool = PortPool()


class default_str(str): pass


def main():
    ap = ArgumentParser(
        description = __doc__,
    )
    arg = ap.add_argument

    arg("config",
        help = "Python script instantiating `Q3T`"
    )
    arg("--ack",
        help = "set RSP `noack` to `False`",
        action = "store_true",
    )
    arg("-v", "--verbose",
        action = "count",
        default = 1,
        help = "+1 to verbocity; 1: more q3t messages, 2: + rsp messages"
    )
    arg("-q", "--quiet",
        action = "count",
        default = 0,
        help = "-1 to verbocity"
    )
    arg("-p", "--prefix",
        help = "test expression prefix",
        default = default_str(">>>"),
    )
    arg("-t", "--timeout",
        default = 5.0,
        type = float,
        help = "stop the emulator if no breakpoints hit during timeout",
    )
    arg("-f", "--failures",
        type = int,
        metavar = "F",
        help = "run each test till F failures, 0 - no limit",
    )
    arg("--print-map",
        action = "store_true",
        help = "print address map (addr to src:line) for each binary",
    )
    arg("--infix",
        default = default_str("q3t"),
        help = "a symbol with such an infix in name is used as a breakpoint",
    )
    arg("-a", "--auto-bps",
        action = "store_true",
        help = "a break point is automatically created for each test"
        " expression without a symbol nearby"
        ,
    )

    args = ap.parse_args()

    verbose = args.verbose - args.quiet
    quiet = verbose < 2
    no_ack = not args.ack
    timeout = args.timeout
    failures = args.failures

    config = read_q3t_config(args.config)
    config_dir_name = config.dir_path

    exit_code = 0

    bp_infix = args.infix
    if isinstance(bp_infix, default_str):
        bp_infix = config.bp_infix or bp_infix

    expr_prefix = args.prefix
    if isinstance(expr_prefix, default_str):
        expr_prefix = config.expr_prefix or expr_prefix

    test_state_kw = dict(
        verbose = verbose,
        timeout = timeout,
        bp_infix = bp_infix,
        expr_prefix = expr_prefix,
    )
    if failures is not None:
        test_state_kw["failures"] = failures
    if args.auto_bps:
        test_state_kw["auto_bps"] = True

    bins_n = len(config.bins)
    for bin_i, bin_file in enumerate(config.bins, 1):
        bin_file_path = bin_file
        if not isfile(bin_file_path):
            bin_file_path = join(config_dir_name, bin_file)
        if not isfile(bin_file_path):
            print("%u/%u: no such file %r" % (bin_i, bins_n, bin_file_path))
            continue

        bin_file_path = abspath(bin_file_path)

        ts = Q3TTestState(**test_state_kw)

        print("%u/%u: loading %r" % (bin_i, bins_n, bin_file_path))

        ts.parse_elf(bin_file_path)

        if args.print_map:
            print_addr2srclines_map(ts.a2sl)

        if not ts.breakpoints:
            ts.print_brs_info()
            continue

        if verbose > 0:
            ts.print_brs_info()

        gdb_port = port_pool.alloc_port()
        if verbose:
            print("gdb_port: " + str(gdb_port))
        qmp_port = port_pool.alloc_port()
        if verbose:
            print("qmp_port: " + str(qmp_port))

        emu_args = list(config.args)

        args_ns = dict(
            bin = ts.bin_file_name,
            gdb_port = str(gdb_port),
            cwd = ts.bin_file_dir,
            qmp_port = str(qmp_port),
        )

        emu_args.extend(("-gdb", "tcp:localhost:{gdb_port},nowait"))
        emu_args.extend(("-qmp", "tcp:localhost:{qmp_port},server,nowait"))

        final_emu_args = []

        for arg in emu_args:
            arg = arg.format_map(args_ns)
            final_emu_args.append(arg)

        if "-S" not in final_emu_args:
            final_emu_args.append("-S")

        print("starting emulator...")
        if verbose:
            print("\n\t".join(repr(a) for a in final_emu_args))

        emu_p = Popen(final_emu_args,
            stdin = PIPE,
            cwd = args_ns["cwd"],
        )

        if verbose:
            print("pid: " + str(emu_p.pid))

        try:
            wait_for_tcp_port(qmp_port)

            qmp = QMP(qmp_port)

            wait_for_tcp_port(gdb_port)

            rsp = config.rsp(gdb_port,
                noack = no_ack,
                verbose = verbose > 1,
            )

            disp = CLICoDispatcher()
            disp.enqueue(ts.co_main(qmp, rsp, quiet = quiet))
            disp.dispatch_all()
        finally:
            emu_p.wait()
            port_pool.free_port(qmp_port)
            port_pool.free_port(gdb_port)

        if ts.result != "PASSED":
            exit_code -= 1

    return exit_code


if __name__ == "__main__":
    exit(main() or 0)
