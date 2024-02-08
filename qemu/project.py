__all__ = [
    "QProject"
]

from .build import (
    register_in_build_system,
    register_src_in_build_system,
)
from common import (
    callco,
    co_find_eq,
    makedirs,
    same_sets,
)
from .cpu import (
    CPUDescription,
)
from libe.common.shadow_open import (
    shadow_open,
)
from .machine_description import (
    MachineNode,
)
from source import (
    disable_auto_lock_inclusions,
    enable_auto_lock_inclusions,
    Source,
)
from .version_description import (
    QemuVersionDescription,
)

from itertools import (
    count,
)
from os.path import (
    isabs,
    join,
    normpath,
    relpath,
    split,
)


class QProject(object):

    def __init__(self,
        descriptions = None
    ):
        self.descriptions = []

        if descriptions is not None:
            for d in descriptions:
                if d.project is not None:
                    raise ValueError("The description '" + d.name
                        +"' is already in another project."
                    )
                else:
                    self.add_description(d)

    def add_description(self, desc):
        desc.project = self
        self.descriptions.append(desc)

    def remove_description(self, desc):
        self.descriptions.remove(desc)
        desc.project = None

    def gen_uniq_desc_name(self):
        for i in count(0):
            cand = "description" + str(i)
            try:
                next(self.find(name = cand))
            except StopIteration:
                return cand

    def find(self, **kw):
        return co_find_eq(self.descriptions, **kw)

    def find1(self, **kw):
        return next(self.find(**kw))

    def gen_all(self, *args, **kw):
        "Backward compatibility wrapper for co_gen_all"
        callco(self.co_gen_all(*args, **kw))

    def co_gen_all(self, qemu_src, **gen_cfg):
        disable_auto_lock_inclusions()
        qvd = QemuVersionDescription.current

        new_targets = set()
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                new_targets.add(desc.directory)

        if new_targets:
            gen_cfg["known_targets"] = (
                gen_cfg.get("known_targets", set()) | new_targets
            )

        # Firstly, generate all CPUs
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                yield desc.gen_type().co_gen(qemu_src, **gen_cfg)

                enable_auto_lock_inclusions()
                # Re-init cache to prevent problems with same named types
                qvd.forget_cache()
                yield qvd.co_init_cache()
                # Replace forgotten dirty cache with new clean one
                qvd.qvc.use()
                disable_auto_lock_inclusions()

        # Secondly, generate all devices
        for desc in self.descriptions:
            if not isinstance(desc, (CPUDescription, MachineNode)):
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        # Lastly, generate machines
        for desc in self.descriptions:
            if isinstance(desc, MachineNode):
                desc.link()
                yield self.co_gen(desc, qemu_src, **gen_cfg)

        enable_auto_lock_inclusions()

    def gen(self, *args, **kw):
        "Backward compatibility wrapper for co_gen"
        callco(self.co_gen(*args, **kw))

    def co_gen(self, desc, src,
        with_chunk_graph = False,
        intermediate_chunk_graphs = False,
        known_targets = None,
        with_debug_comments = False,
        include_paths = tuple(),
        **_
    ):
        qom_t = desc.gen_type()

        yield qom_t.co_gen_sources()

        for s in qom_t.sources:
            spath = join(src, s.path)
            sdir, sname = split(spath)

            yield True

            makedirs(sdir, exist_ok = True)

            yield True

            f = s.generate()

            if with_chunk_graph:
                yield True
                f.gen_chunks_gv_file(spath + ".chunks-before-gen.gv")

            yield True

            if intermediate_chunk_graphs:
                graphs_prefix = spath + ".chunks"
            else:
                graphs_prefix = None

            with shadow_open(spath) as stream:
                f.generate(stream,
                    graphs_prefix = graphs_prefix,
                    gen_debug_comments = with_debug_comments,
                    include_paths = include_paths
                )

            if with_chunk_graph:
                yield True
                f.gen_chunks_gv_file(spath + ".chunks-after-gen.gv")

            yield True
            f.update_origin_inclusions()

            # Only sources need to be registered in the build system
            if type(s) is not Source:
                continue

            directory = join("hw", desc.directory)

            yield
            register_in_build_system(src, directory, known_targets)

            yield True
            register_src_in_build_system(src, sname, directory)

    # TODO: add path to `QProject`
    # TODO: def lookup_path

    def replace_relpaths_to_abspaths(self, path):
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                info_path = desc.info_path
                if not info_path:
                    continue
                if not isabs(info_path):
                    desc.info_path = normpath(join(path, info_path))

    def replace_abspaths_to_relpaths(self, path):
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                info_path = desc.info_path
                if not info_path:
                    continue
                if isabs(info_path):
                    desc.info_path = relpath(info_path, start = path)

    def __var_base__(self):
        return "project"

    def __same__(self, o):
        if type(self) is not type(o):
            return False

        # Descriptions order is not significant
        if same_sets(self.descriptions, o.descriptions):
            return True
        return False

    __pygen_deps__ = ("descriptions",)

    def __gen_code__(self, gen):
        gen.gen_code(self)
