#!/usr/bin/python

from common import (
    execfile,
    makedirs,
    pythonize,
)
import qdt
from qemu import (
    CPUDescription,
    qvd_load_with_cache,
)

from argparse import (
    ArgumentParser,
    ArgumentTypeError,
)
from os.path import (
    dirname,
    isdir,
)
from traceback import (
    print_exc,
)


def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(string + " is not directory")
    return string

def main():
    parser = ArgumentParser(
        description = "QEMU Project Generator."
            " The tool generates boilerplate source files into QEMU source"
            " tree according to settings read from project script."
            " Related existing files are updated.",
    )
    arg = parser.add_argument

    arg(
        "--qemu-build", "-b",
        default = None,
        type = arg_type_directory,
        metavar = "/path/to/qemu/build/directory",
        help = "Override QEMU build path of the project.",
    )
    arg(
        "--target-version", "-t",
        default = None,
        metavar = "<tree-ish>", # like in Git's docs
        help = "Assume given version of Qemu."
        " Overrides project's target_version.",
    )
    arg(
        "--gen-header-tree",
        default = None,
        metavar = "header_tree.gv",
        help = "Output QEMU header inclusion graph in Graphviz format.",
    )
    arg(
        "--gen-chunk-graphs",
        action = "store_true",
        help = "Generate Graphviz files with graph of chunks per each"
            " generated source.",
    )
    arg(
        "--gen-intermediate-chunk-graphs",
        action = "store_true",
        help = "Generate Graphviz files with intermediate graph of chunks"
            " during header inclusion optimization for each generated"
            " source.",
    )
    arg(
        "--gen-debug-comments",
        action = "store_true",
        help = "Generate source files with debug comments.",
    )
    arg(
        "--no-i3s",
        action = "store_true",
        help = "Disable automatic CPU semantics translation.",
    )
    arg(
        "--no-instruction-tree-optimizations",
        action = "store_true",
        help = "Disable optimizations when building an instruction tree.",
    )
    arg(
        "--instruction-tree-lookahead",
        action = "store_true",
        help = "Enable lookahead approach when building"
            " an instruction tree.",
    )
    arg(
        "--dry-run",
        action = "store_true",
        help = "Do not generate project.",
    )
    arg(
        "--output", "-o",
        default = None,
        metavar = "/path/to/output/script.py",
        help = "Write project script to file with path given.",
    )
    arg(
        "scripts",
        nargs = "+",
        help = "Python scripts containing definitions of"
            " projects to generate. Before generation projects are merged."
            " First project settings have priority.",
    )

    arguments = parser.parse_args()

    scripts = arguments.scripts

    project = None

    for script in scripts:
        loaded = dict(qdt.__dict__)
        try:
            execfile(script, loaded)
        except:
            print("Cannot load configuration from '%s'" % script)
            print_exc()
            return -1

        projects = []
        for v in loaded.values():
            if isinstance(v, qdt.QProject):
                v.file_name = script  # it's known exactly
                projects.append(v)

        if not projects:
            print("Script '%s' does not define a project to generate." % (
                script,
            ))
            return -1

        for v in projects:
            if project is None:
                project = v
            else:
                project.merge(v)

    if arguments.qemu_build is None:
        qemu_build_path = getattr(project, "build_path", None)
    else:
        qemu_build_path = arguments.qemu_build
    if not qemu_build_path: # None, empty
        qemu_build_path = "."

    version = arguments.target_version

    if version is None:
        version = getattr(project, "target_version", None)

    try:
        qvd = qvd_load_with_cache(qemu_build_path, version = version)
    except:
        print("QVD loading failed")
        print_exc()
        return -1

    qvd.use()

    if arguments.gen_header_tree is not None:
        qvd.qvc.stc.gen_header_inclusion_dot_file(arguments.gen_header_tree)

    if arguments.no_instruction_tree_optimizations:
        for desc in project.descriptions:
            if isinstance(desc, CPUDescription):
                desc.instruction_tree_optimizations = False

    if arguments.instruction_tree_lookahead:
        for desc in project.descriptions:
            if isinstance(desc, CPUDescription):
                desc.instruction_tree_lookahead = True

    if not arguments.dry_run:
        project.gen_all(qvd.src_path,
            intermediate_chunk_graphs
                = arguments.gen_intermediate_chunk_graphs,
            with_chunk_graph = arguments.gen_chunk_graphs,
            known_targets = qvd.qvc.known_targets,
            with_debug_comments = arguments.gen_debug_comments,
            translate_cpu_semantics = not arguments.no_i3s,
            include_paths = tuple(path for path, __ in qvd.include_paths)
        )

    output = arguments.output
    if output:
        output_dir = dirname(output)
        if output_dir:
            makedirs(output_dir, exist_ok = True)
        pythonize(project, output)

    return 0

if __name__ == "__main__":
    exit(main())
