__all__ = [
    "QProject"
]

from common import (
    callco,
    co_find_eq,
    caller_file_name,
    same_sets,
    shadow_open,
)
from .cpu import (
    CPUDescription,
)
from source import (
    disable_auto_lock_inclusions,
    enable_auto_lock_inclusions,
)

from itertools import (
    count,
)
from os.path import (
    abspath,
    dirname,
    exists,
    join,
)


class QProject(object):

    def __init__(self,
        descriptions = None,
        file_name = None,
        **compat
    ):
        if file_name is None:
            file_name = caller_file_name()

        self.file_name = file_name

        self.descriptions = []

        if descriptions is not None:
            for d in descriptions:
                if d.project is not None:
                    raise ValueError("The description '" + d.name
                        +"' is already in another project."
                    )
                else:
                    self.add_description(d)

        self.compat = compat

    def merge(self, project):
        for d in project.descriptions:
            project.remove_description(d)
            self.add_description(d)

        setdefault = self.compat.setdefault
        for kv in project.compat.items():
            setdefault(*kv)

    @property
    def file_name(self):
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        self._file_name = file_name
        if file_name is None:
            self._project_root = None
        else:
            self._project_root = dirname(abspath(file_name))

    @property
    def project_root(self):
        return self._project_root

    def lookup_path(self, suffix):
        for path in self.iter_possible_paths(suffix):
            if exists(path):
                return abspath(path)
        raise ValueError("can't lookup path %r" % suffix)

    def iter_possible_paths(self, suffix):
        root = self.project_root
        if root is not None:
            yield join(root, suffix)
        yield suffix

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

        new_targets = set()
        for desc in self.descriptions:
            if isinstance(desc, CPUDescription):
                new_targets.add(desc.directory)

        if new_targets:
            gen_cfg["known_targets"] = (
                gen_cfg.get("known_targets", set()) | new_targets
            )

        for desc in sorted(self.descriptions):
            yield desc.co_gen(qemu_src, **gen_cfg)

        enable_auto_lock_inclusions()

    def gen(self, desc, *args, **kw):
        "Backward compatibility wrapper for co_gen"
        callco(desc.co_gen(*args, **kw))

    def __var_base__(self):
        return "project"

    def __same__(self, o):
        if type(self) is not type(o):
            return False

        # Descriptions order is not significant
        if same_sets(self.descriptions, o.descriptions):
            return True
        return False

    __pygen_deps__ = (
        "compat",
        "descriptions",
    )

    def __gen_code__(self, gen):
        gen.reset_gen(self)
        gen.gen_args(self)
        if self.compat:
            for attr, val in self.compat.items():
                gen.gen_field(attr + " = ")
                gen.pprint(val)
        gen.gen_end()
