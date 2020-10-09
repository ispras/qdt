from os import (
    listdir,
)
from ..lazy import (
    lazy,
)


class PathBacked(object):

    def __init__(self, ctx, relpath):
        assert isinstance(relpath, tuple)

        self._ctx = ctx
        self._relpath = relpath

    @lazy
    def os_path(self):
        return self._ctx.get_os_path(self._relpath)

    @lazy
    def creator(self):
        raise NotImplementedError

    @lazy
    def creation_time(self):
        raise NotImplementedError


class PathBackedCache(object):

    def __init__(self, ctx, rel_dir_path, Class):
        assert issubclass(Class, PathBacked)
        assert isinstance(rel_dir_path, tuple)

        self._ctx = ctx
        self._rel_dir_path = rel_dir_path
        self._dir_path = ctx.get_os_path(rel_dir_path)
        self._Class = Class
        self._cache = {}

    def __getitem__(self, name):
        try:
            fb = self._cache[name]
        except KeyError:
            fb = self._Class(self._ctx, self._rel_dir_path + (name,))
            self._cache[name] = fb
        return fb

    def iter_file_backed(self):
        dir_path = self._dir_path

        Class = self._Class
        cache = self._cache
        ctx = self._ctx
        rel_dir_path = self._rel_dir_path

        for name in listdir(dir_path):
            backed = cache.get(name)
            if backed is None:
                backed = Class(ctx, rel_dir_path + (name,))
                cache[name] = backed

            yield backed
