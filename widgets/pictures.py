__all__ = [
    "try_photo_image"
  , "Pictures"
  , "pic_path"
  , "pic_dir"
]

from os.path import (
    dirname,
    exists,
    join,
)

from six.moves.tkinter import (
    PhotoImage,
)


pic_dir = dirname(__file__)


def try_photo_image(path, *fallback):
    if not exists(path):
        path = pic_path(path)
    try:
        return PhotoImage(
            file = path,
        )
    except:
        if not fallback:
            raise
    return try_photo_image(*fallback)


class Pictures(object):

    def __init__(self, **pictures):
        self.pictures = pictures
        self.__hasattr__ = pictures.__contains__
        self.cache = dict()

    def provide(self, name):
        try:
            return self.cache[name]
        except KeyError:
            path = self.pictures[name]
            if isinstance(path, str):
                pi = try_photo_image(path)
            else:
                pi = try_photo_image(*path)
            self.cache[name] = pi
            return pi

    def __getattr__(self, name):
        try:
            return self.provide(name)
        except:
            raise AttributeError(name)


def pic_path(suffix):
    return join(pic_dir, suffix)
