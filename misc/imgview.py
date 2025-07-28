#!/usr/bin/env python3

# configure PYTHONPATH
from os.path import (
    dirname,
)
from sys import (
    path as PYTHONPATH,
)
DIR = dirname(__file__)
PYTHONPATH.insert(0, dirname(DIR))

from common import (
    byN,
)
from widgets import (
    add_scrollbars_native,
    BOTH,
    Chainview,
    GUIFrame,
    GUITk,
    Pictures,
    pic_path,
)

from argparse import (
    ArgumentParser,
)
from itertools import (
    chain,
)
from os import (
    listdir,
    stat,
)
from os.path import (
    exists,
    isdir,
    isfile,
    join,
)
from six.moves import (
    zip_longest,
)
from six.moves.tkinter import (
    BROWSE,
    END,
    X,
)
from six.moves.tkinter_ttk import (
    Treeview,
)

FS_EMPTY = frozenset()

def common_supers(*class_iterables):
    i = iter(class_iterables)
    for classes in i:
        common = set(classes)
        break
    else:
        return FS_EMPTY

    while common:
        for classes in i:
            for ccls in tuple(common):
                for icls in classes:
                    if ccls is icls:
                        break
                    if issubclass(icls, ccls):
                        break
                    if issubclass(ccls, icls):
                        # icls is common base for (icls, rcls)
                        common.add(icls)
                else:
                    common.remove(ccls)
            break
        else:
            break

    return common


class ImageView:

    def __init__(self, image):
        self._image = image


class SubimageProvider(ImageView):

    def __iter__(self):
        return self._image.__iter_names__()

    def __contains__(self, name):
        return self._image.__contains_subimage__(name)

    def __getitem__(self, name):
        return self._image.__get_subimage__(name)


class StatView(ImageView):

    def __iter__(self):
        return self._image.__iter_stat__()

    def __contains__(self, name):
        return self._image.__contains_stat__(name)

    def __getitem__(self, name):
        return self._image.__get_stat__(name)


class SummaryView(ImageView):

    def __str__(self):
        return self._image.__summary_str__()


class Image:

    __views__ = ()

    @property
    def is_directory_like(self):
        return bool(common_supers((SubimageProvider,), self.__views__))

    def view_classes(self, *view_classes):
        return common_supers(self.__views__, view_classes)

    def view_class(self, *view_classes):
        avl = self.view_classes(*view_classes)
        if not avl:
            if not view_classes:
                raise ValueError("a view class is required")
            raise NotImplementedError(view_classes)
        return next(iter(avl))

    def view(self, *view_classes):
        return self.view_class(*view_classes)(self)


class VirtualDirectory(Image):

    __views__ = (
        SubimageProvider,
    )

    def __init__(self, parent = None):
        self._parent = parent
        self._images = {}

    def __contains__(self, name):
        return name in self._images

    def __setitem__(self, name, image):
        assert self._images.setdefault(name, image) is image

    def __getitem__(self, name):
        return self._images[name]

    def __delitem__(self, name):
        del self._images[name]

    def override(self, name, image):
        try:
            del self[name]
        except KeyError:
            pass
        self[name] = image

    def __iter_names__(self):
        return iter(self._images)

    __get_subimage__ = __getitem__
    __contains_subimage__ = __contains__


class Merged(Image):

    def __init__(self, *images):
        self._merged = set(images)

    def merge(self, image):
        self._merged.add(image)

    def __iter__(self):
        return iter(self._merged)

    IMPLEMENTED_VIEWS = set([SubimageProvider, StatView])

    @property
    def __views__(self):
        common = common_supers(*(i.__views__ for i in self._merged))
        return common & self.IMPLEMENTED_VIEWS

    def __iter_names__(self):
        return self.iter_views_names(SubimageProvider)

    def __contains_subimage__(self, name):
        for n in self.iter_views_names(SubimageProvider):
            if n == name:
                return True
        return False

    def __get_subimage__(self, name):
        return Merged(*(
            i for i in self.iter_views_values(name, SubimageProvider)
                if i is not None
        ))

    def __iter_stat__(self):
        return self.iter_views_names(StatView)

    def __contains_stat__(self, name):
        for n in self.iter_views_names(StatView):
            if n == name:
                return True
        return False

    def __get_stat__(self, name):
        return tuple(self.iter_views_values(name, StatView))

    def iter_views(self, *view_classes):
        for i in self._merged:
            try:
                yield i.view(*view_classes)
            except NotImplementedError:
                yield None

    def iter_views_values(self, name, *view_classes):
        for v in self.iter_views(*view_classes):
            if v is None:
                yield v
            if name in v:
                yield v[name]
            else:
                yield None

    def iter_views_names(self, *view_classes):
        yielded = set()
        skip = yielded.add
        for v in self.iter_views(*view_classes):
            if v is None:
                continue
            for n in v:
                if n in yielded:
                    continue
                yield n
                skip(n)


class FSNode(Image):

    def __init__(self, path, parent = None):
        self._path = path
        self._parent = parent
        self._cache = {}

    @property
    def __views__(self):
        return tuple(self.iter_views())

    def iter_views(self):
        if isdir(self._path):
            yield SubimageProvider
        yield StatView
        yield SummaryView

    def __iter_names__(self):
        return iter(listdir(self._path))

    def __contains_subimage__(self, name):
        return name in listdir(self._path)

    def __get_subimage__(self, name):
        cache = self._cache
        ret = cache.get(name)
        if ret is None:
            subpath = join(self._path, name)
            if (
                exists(subpath)
                # Broken symlinks are present in `listdir` but `not exists`.
             or name in listdir(self._path)
            ):
                ret = FSNode(subpath, parent = self)
                cache[name] = ret
            else:
                raise KeyError(name)
        return ret

    DIR_AUTO_STATS = ("n_files", "n_dirs", "n_total",)

    def __iter_stat__(self):
        path = self._path

        if isfile(path):
            return (n for n in dir(stat(path)) if n.startswith("st_"))

        if isdir(path):
            return chain(
                (n for n in dir(stat(path)) if n.startswith("st_")),
                self.DIR_AUTO_STATS
            )

    def __contains_stat__(self, name):
        path = self._path

        if isfile(path):
            return hasattr(stat(path), name)

        if isdir(path):
            return (name in self.DIR_AUTO_STATS) \
                or hasattr(stat(path), name)

    def __get_stat__(self, name):
        path = self._path

        if isfile(path):
            return getattr(stat(path), name)

        if isdir(path):
            if name == "n_total":
                return len(tuple(self.__iter_names__()))
            if name == "n_files":
                count = 0
                for n in self.__iter_names__():
                    count += isfile(join(path, n))
                return count
            if name == "n_dirs":
                count = 0
                for n in self.__iter_names__():
                    count += isdir(join(path, n))
                return count
            return getattr(stat(path), name)

    BYTE_MULTS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB")

    def __summary_str__(self):
        path = self._path

        if isfile(path):
            st = stat(path)
            sz = st.st_size
            prev_sz = 0
            scale = 0
            while sz >= 1024:
                prev_sz = sz & 0x3FF
                sz >>= 10
                scale += 1

            try:
                ss = self.BYTE_MULTS[scale]
            except IndexError:
                ss = "!iB"

            return "F %.1f%s" % (sz + prev_sz / 1024.0, ss)

        if isdir(path):
            nf, nd, nt = 0, 0, 0
            for n in self.__iter_names__():
                np = join(path, n)
                if isfile(np):
                    nf += 1
                elif isdir(np):
                    nd += 1
                nt += 1

            return "D %d/%d/%d" % (nd, nf, nt)

        return "?"


def iter_tree_lines(root, max_depth = None, indent = "\t"):
    if max_depth:
        max_depth -= 1

    views = tuple(root.__views__)
    for View in views:
        if issubclass(View, SubimageProvider):
            if max_depth == 0:
                yield "..."
                return
            view = View(root)
            for name in view:
                yield name
                img = view[name]
                for line in iter_tree_lines(img,
                    max_depth = max_depth,
                    indent = indent,
                ):
                    yield indent + line
            return
    for View in views:
        if issubclass(View, SubimageProvider):
            if max_depth == 0:
                yield "..."
                return
            view = View(root)
            for name in view:
                yield name
            return


class ImageViewWidget:

    EVENT_ENTER_SUBIMAGE = "<<EnterSubimage>>"

    __view2widget__ = {}

    _image = None

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, image):
        if self._image is image: return
        self.__image_changed__(image)
        self._image = image


class StatFrame(GUIFrame, ImageViewWidget):

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self._tv = tv = Treeview(self,
            show = "tree",
        )
        self._tv_cache = []  # of detached items
        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv, sizegrip = True)

    def __image_changed__(self, image):
        tv = self._tv
        tv_cache = self._tv_cache

        sv = StatView(image)

        # TODO: this may take a while...
        names = sorted(tuple(sv))
        values = {}
        max_cols = 1
        for name in names:
            values[name] = val = sv[name]
            if isinstance(val, (tuple, list)):
                max_cols = max(max_cols, len(val))

        tv.configure(columns = [""] * max_cols)

        for name, ciid in zip_longest(
            names,
            tv.get_children("")
        ):
            if name is None:
                tv.detach(ciid)
                tv_cache.append(ciid)
                continue
            if ciid is None:
                if tv_cache:
                    ciid = tv_cache.pop()
                    tv.move(ciid, "", END)
                else:
                    ciid = tv.insert("", END)

            val = values[name]
            if not isinstance(val, (tuple, list)):
                val = (val,)

            cfg = dict(
                text = name,
                values = val,
            )

            tv.item(ciid, **cfg)

ImageViewWidget.__view2widget__[StatView] = StatFrame


class SubimagesFrame(GUIFrame, ImageViewWidget):

    icons = Pictures(
        subtree = pic_path("subtree.png"),
        opaque  = pic_path("opaque.png"),
    )

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self._tv = tv = Treeview(self,
            show = "tree",
            selectmode = BROWSE,
        )
        self._tv_cache = []  # of detached items
        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv, sizegrip = True)

        tv.bind("<Double-Button-1>", self._on_tv_2b1)
        tv.bind("<Return>", self._on_tv_enter)

    def _on_tv_2b1(self, e):
        tv = e.widget
        iid = tv.identify("item", e.x, e.y)
        if not iid:
            return
        self.subimage_name = tv.item(iid, "text")
        self.event_generate(self.EVENT_ENTER_SUBIMAGE)
        del self.subimage_name

    def _on_tv_enter(self, e):
        tv = e.widget
        sel = tv.get_section()
        if not sel:
            return
        iid = sel[0]
        self.subimage_name = tv.item(iid, "text")
        self.event_generate(self.EVENT_ENTER_SUBIMAGE)
        del self.subimage_name

    def __image_changed__(self, image):
        tv = self._tv
        tv_cache = self._tv_cache
        ico_subtree = self.icons.subtree
        ico_opaque = self.icons.opaque

        sp = SubimageProvider(image)

        for name, ciid in zip_longest(
            # TODO: this may take a while...
            sorted(sp, key = lambda n: (not sp[n].is_directory_like, n)),
            tv.get_children("")
        ):
            if name is None:
                tv.detach(ciid)
                tv_cache.append(ciid)
                continue
            if ciid is None:
                if tv_cache:
                    ciid = tv_cache.pop()
                    tv.move(ciid, "", END)
                else:
                    ciid = tv.insert("", END)

            cfg = dict(
                text = name,
            )

            subimg = sp[name]
            if subimg.is_directory_like:
                cfg["image"] = ico_subtree
            else:
                cfg["image"] = ico_opaque

            tv.item(ciid, **cfg)

ImageViewWidget.__view2widget__[SubimageProvider] = SubimagesFrame


class ImgviewFrame(GUIFrame):

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        self._cv = cv = Chainview(self)
        cv.bind(Chainview.EVENT_SELECT, self._on_chainview_select, "+")
        cv.pack(fill = X)

        self._f_img_widgets = f = GUIFrame(self)
        f.pack(fill = BOTH, expand = True)

        self._img_w_cache = {}

        self._refresh_img_w()

    _tree = None

    @property
    def tree(self):
        return self._tree

    @tree.setter
    def tree(self, tree):
        if tree is self._tree: return
        self._tree = tree
        self._cv.chain = ("/",)
        self._refresh_img_w()

    def _on_chainview_select(self, e):
        self._refresh_img_w()

    def _refresh_img_w(self):
        img = self.tree
        for name in self._cv.subchain[1:]:
            img = SubimageProvider(img)[name]

        f = self._f_img_widgets
        unused = set(f.pack_slaves())

        if img is not None:
            WCls2w = dict((type(w), w) for w in unused)

            available_views = common_supers(
                img.__views__,
                ImageViewWidget.__view2widget__,
            )
            for VCls in available_views:
                WCls = ImageViewWidget.__view2widget__[VCls]

                img_w = WCls2w.pop(WCls, None)

                if img_w is None:
                    img_w = self._img_w_cache.pop(WCls, None)
                else:
                    unused.remove(img_w)

                if img_w is None:
                    img_w = WCls(f)
                    img_w.bind(
                        img_w.EVENT_ENTER_SUBIMAGE,
                        self._on_enter_subimage
                    )

                img_w.pack(fill = BOTH, expand = True)
                img_w.image = img

        for img_w in unused:
            assert img_w is self._img_w_cache.setdefault(
                type(img_w), img_w
            )
            img_w.pack_forget()

    def _on_enter_subimage(self, e):
        siname = e.widget.subimage_name
        cv = self._cv
        cv.chain = cv.subchain + (siname,)
        cv.index = -1


class ImgviewTk(GUITk):

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)
        self.title("Image view")
        self._f = f = ImgviewFrame(self)
        f.pack(fill = BOTH, expand = True)

    @property
    def tree(self):
        return self._f.tree

    @tree.setter
    def tree(self, tree):
        self._f.tree = tree


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("path",
        nargs = "+",
        help = "v/path os/path"
    )

    args = ap.parse_args()

    vroot = VirtualDirectory()

    paths = args.path
    if len(paths) & 1:
        raise ValueError("paths must be paired, 'virtual path' 'OS path'")

    for v_path, os_path in byN(2, paths):
        if not v_path:
            raise ValueError("%r: no virtual path provided" % (os_path,))
        d = vroot
        for n in v_path.split('/'):
            if isinstance(d, Merged):
                for img in d:
                    if isinstance(img, VirtualDirectory):
                        vd = img
                        break
                else:
                    raise AssertionError
            else:
                assert isinstance(d, VirtualDirectory)
                vd = d
            if n not in vd:
                vd[n] = VirtualDirectory(parent = vd)
            d = vd[n]

        os_node = FSNode(os_path)
        if isinstance(d, VirtualDirectory):
            d._parent.override(n, Merged(d, os_node))
        else:
            d.merge(os_node)

    root = ImgviewTk()
    root.tree = vroot
    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
