__all__ = [
    "Persistent"
]

from os.path import (
    isfile
)
from .pygen import (
    pythonize
)
from .compat import (
    execfile
)
from .extensible import (
    Extensible
)


class Persistent(Extensible):
    """ Given a file name, keeps self attributes in sync with the file.

Example:

with Persistent("my_file", glob = globals()) as ctx:
    do_something(ctx)

Note, `glob` is only required iff `PyGenerator` compatible types are used.

    """

    def __init__(self, file_name, glob = None, version = 1.0, **kw):
        super(Persistent, self).__init__(**kw)
        self._file_name = file_name
        self._globals = {} if glob is None else dict(glob)
        self._version = version

    def _load(self):
        if isfile(self._file_name):
            loaded = {}
            try:
                execfile(self._file_name, self._globals, loaded)
                ctx = loaded["persistent_context"]
            except:
                return

            ctx_version = ctx.pop("_version", self._version)

            for k, v in ctx.items():
                setattr(self, k, v)

            if ctx_version < self._version:
                self.__update__(ctx_version)

    def __update__(self, loaded_version):
        raise NotImplementedError(
            "Update from %f to %f is not implemented" % (
                self._version, loaded_version
            )
        )

    def _save(self):
        pythonize(self, self._file_name)

    def __gen_code__(self, g):
        ctx = self._dict
        ctx["_version"] = self._version
        g.pprint(ctx)

    def __var_base__(self):
        return "persistent_context"

    def __enter__(self):
        self._load()
        return self

    def __exit__(self, e, *_): # value, traceback
        # If an exception happened, do not save
        if e is None:
            self._save()
