from argparse import (
    ArgumentTypeError,
    ArgumentParser
)
from os.path import (
    isdir
)
from qemu import (
    TargetCPU,
    qvd_load_with_cache
)
from common import (
    execfile
)
from traceback import (
    print_exc
)
import cpu

def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(string + " is not directory")
    return string

def main():
    argparser = ArgumentParser()
    argparser.add_argument(
        "--qemu-build", "-b",
        default = ".",
        type = arg_type_directory,
        metavar = "/path/to/qemu/build/directory",
        help = "Override QEMU build path of the architecture."
    )
    argparser.add_argument(
        "--target-version", "-t",
        default = None,
        metavar = "<tree-ish>", # like in Git's docs
        help = "Assume given version of Qemu."
        " Overrides architecture's target_version."
    )
    argparser.add_argument(
        "--verbose", "-v",
        action = "store_true",
        help = "Produce an additional output when creating parsing tree."
    )
    argparser.add_argument(
        "-d",
        action = "store_true",
        help = "Generate ARCH decoder tests."
    )
    argparser.add_argument(
        "--gen-chunk-graphs",
        action = "store_true",
        help = "Generate Graphviz files with graph of chunks per each "
        "generated source."
    )
    argparser.add_argument(
        "--gen-debug-comments",
        action = "store_true",
        help = "Generate source files with debug comments."
    )
    argparser.add_argument(
        "--gen-header-tree",
        default = None,
        metavar = "header_tree.gv",
        help = "Output QEMU header inclusion graph in Graphviz format."
    )
    argparser.add_argument(
        "script",
        help = "A Python script containing description of architecture."
    )

    args = vars(argparser.parse_args())

    try:
        qvd = qvd_load_with_cache(
            args["qemu_build"],
            version = args["target_version"]
        )
    except:
        print("QVD loading failed")
        print_exc()
        return -1

    qvd.use()

    script = args["script"]

    loaded_variables = dict(cpu.__dict__)
    try:
        # Same object must be used for both globals and locals.
        # This allows to easily define and use auxiliary variables and
        # functions in configuration.
        # https://stackoverflow.com/questions/45132645/list-comprehension-in-exec-with-empty-locals-nameerror
        execfile(script, loaded_variables)
    except:
        print("Cannot load architecture from '%s'" % script)
        print_exc()
        return -1

    for v in loaded_variables.values():
        if isinstance(v, TargetCPU):
            target_cpu = v
            break
    else:
        print("Script '%s' does not define a architecture" % script)
        return -1

    if args["gen_header_tree"] is not None:
        qvd.qvc.stc.gen_header_inclusion_dot_file(args["gen_header_tree"])

    target_cpu.gen_all(qvd.src_path,
        with_chunk_graph = args["gen_chunk_graphs"],
        with_debug_comments = args["gen_debug_comments"]
    )

    return 0

if __name__ == "__main__":
    exit(main())
