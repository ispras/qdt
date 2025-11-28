__all__ = [
    "PatchImplType"
  , "PatchImplDescription"
]

from common import (
    co_process,
    mlget as _,
)
from .qom import (
    QOMType,
)
from .qom_desc import (
    descriptionOf,
    QOMDescription,
)

from collections import (
    OrderedDict,
)
from os import (
    listdir,
)
from os.path import (
    abspath,
    basename,
    isdir,
    isfile,
    join,
)
from subprocess import (
    run,
)


class PatchImplType(QOMType):
    """ `patch` based Implementation.
Not a QOM type.
It's a way to overwrite existing or generated sources.
New sources can be added too, but consider `ImmImplDescription`.
    """

    __attribute_info__ = OrderedDict((
        ("path", { "short": _("Path"), "input": str }),
        ("gen_order",
            { "short": _("Generation Order"), "input": int }
        ),
        ("patch_args",
            { "short": _("`patch` arguments"), "input": str },
        ),
    ))

    def __init__(self, name, directory,
        path = "patches",
        patch_args = "-p1 --no-backup-if-mismatch --force -i {patch}",
        gen_order = 2, # Used by QOMDescription.
        **__
    ):
        """
@param name:
    For user convenience only.

@param directory:
    A directory in Qemu source tree where the `patch` utility is run.

@param path:
    A path relative to the project or absolute to the patch files or
    directory tree with patch files.
    Patches are `sorted` by `path` relative paths.

@param patch_args:
    A `.format` string to generate arguments for `patch` command.

@param gen_order:
    Less values are generated earlier.
        """
        self.name = name
        self.directory = directory
        self.path = path
        self.patch_args = patch_args


def lower_string_tuple(strings):
    return tuple(
        (s.lower() if isinstance(s, str) else lower_string_tuple(s))
            for s in strings)


@descriptionOf(PatchImplType)
class PatchImplDescription(QOMDescription):

    def co_gen(self, src, *__, **___):
        path = self.path
        ospath = self.project.lookup_path(path)

        if isdir(ospath):
            # The patches root directory itself is not accounted.
            stack = list(
                (join(ospath, iname), ())
                        for iname in listdir(ospath)
            )
        else:
            stack = [(ospath, ())]

        pop = stack.pop
        extend = stack.extend
        patches = []

        while stack:
            yield True
            ospath, infix = pop()

            name = basename(ospath)

            if isfile(ospath):
                infixed_name = infix + (name,)
                patches.append((infixed_name, ospath, infix))
                continue

            if isdir(ospath):
                extend(
                    (
                        join(ospath, iname),
                        infix + (name,),
                    )
                        for iname in listdir(ospath)
                )
                continue

            print("%s: unsupported patch path" % (ospath,))

        patch_args = self.patch_args
        cwd = abspath(join(src, self.directory))

        for __, ospath, __ in sorted(patches, key = lower_string_tuple):
            # TODO: should we change `patch` CWD according to patch file
            # relative name?
            print("Applying path %r" % ospath)
            yield co_process(
                run,
                "patch " + patch_args.format(patch = ospath),
                shell = True,
                cwd = cwd,
            )
