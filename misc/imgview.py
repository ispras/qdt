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
    AutoPanedWindow,
    BOTH,
    Chainview,
    GUIFrame,
    GUITk,
    Pictures,
    pic_path,
    TasksFrame,
    tk_delayed,
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
    split,
)
from six.moves import (
    zip_longest,
)
from six.moves.tkinter import (
    BROWSE,
    END,
    VERTICAL,
    X,
)
from six.moves.tkinter_ttk import (
    Treeview,
)
from time import (
    time,
)

# temp debug stuff
import linecache
import tracemalloc


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


class Observed(dict):

    def __init__(self, obj):
        self._obj = obj

    def __missing__(self, event):
        cbs = list()
        self[event] = cbs
        return cbs


class ObjectObserver(dict):

    def __missing__(self, obj):
        ret = Observed(obj)
        self[obj] = ret
        return ret

    def observe(self, cb, obj, *events):
        event2cbs = self[obj]
        if events:
            for event in events:
                event2cbs[event].append(cb)
        else:
            event2cbs[None].append(cb)

    def forget(self, cb, *obj_and_events):
        if not obj_and_events:
            for obj in tuple(self):
                self.forget(cb, obj)
            return
        obj, *events = obj_and_events
        event2cbs = self.pop(obj, None)
        if event2cbs is None:
            return
        pop = event2cbs.pop
        if not events:
            events = tuple(event2cbs)
        for event in events:
            cbs = pop(event, None)
            if cbs is None:
                continue
            try:
                cbs.remove(cb)
            except ValueError:
                pass
            if cbs:
                event2cbs[event] = cbs
        if event2cbs:
            self[obj] = event2cbs

    def emit(self,obj, *events, **kw):
        event2cbs = self.pop(obj, None)
        if event2cbs is None:
            return
        pop = event2cbs.pop
        for event in events:
            cbs = pop(event, None)
            if cbs is None:
                continue
            cbs2 = list()
            again = cbs2.append
            for cb in cbs:
                if cb(**kw):
                    again(cb)
            if cbs2:
                event2cbs[event] = cbs2
        cbs = pop(None, None)
        if cbs is not None:
            kw["events"] = events
            cbs2 = list()
            again = cbs2.append
            for cb in cbs:
                if cb(**kw):
                    again(cb)
            if cbs2:
                event2cbs[None] = cbs2
        if event2cbs:
            self[obj] = event2cbs

    __call__ = emit


obs = ObjectObserver()

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

    def equals_to(self, v):
        for __, eq in self.iter_compare(v):
            if not eq:
                return False
        return True

    def iter_compare(self, v):
        for name, vs, vv in self.iter_zip(v):
            yield name, (vs == vv)

    def iter_zip(self, v):
        svs = dict((name, self[name]) for name in self)
        for name in v:
            vv = v[name]
            yield name, svs.pop(name, None), vv
        for name, sv in svs.items():
            yield name, sv, None


class BackupView(ImageView):

    class UNIQUE: pass
    class DIFFERENT: pass
    class EQUAL: pass

    def __iter__(self):
        return self._image.__iter_backup__()

    def __contains__(self, name):
        return self._image.__contains_backup__(name)

    def __getitem__(self, name):
        return self._image.__get_backup__(name)


class SummaryView(ImageView):

    def __str__(self):
        return self._image.__summary_str__()


class BackupStatView(StatView):
    "backup relevant stats only"

    def __iter__(self):
        return self._image.__iter_backup_stat__()


IS_DIRECTORY_LIKE_VIEW = lambda VCls : issubclass(VCls, SubimageProvider)


class Image:

    __views__ = ()

    @property
    def is_directory_like(self):
        for v in self.__views__:
            if IS_DIRECTORY_LIKE_VIEW(v):
                return True
        return False

    def iter_views_filtered(self, *view_classes):
        for v in self.__views__:
            if issubclass(v, view_classes):
                yield v

    def view_classes(self, *view_classes):
        return list(self.iter_views_filtered(*view_classes))

    def view_class(self, *view_classes):
        avl = self.view_classes(*view_classes)
        if not avl:
            if not view_classes:
                raise ValueError("a view class is required")
            raise NotImplementedError(view_classes)
        return next(iter(avl))

    def view(self, *view_classes):
        return self.view_class(*view_classes)(self)

    def observe(self, cb, *events):
        obs.observe(cb, self, *events)

    def forget(self, cb, *events):
        obs.forget(cb, self, *events)


class VirtualDirectory(Image):

    __views__ = (
        SubimageProvider,
        StatView,
        SummaryView,
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

    def __summary_str__(self):
        nf, nd, nt = 0, 0, 0
        for i in self._images.values():
            if i.is_directory_like:
                nd += 1
            else:
                nf += 1
            nt += 1

        return "VD %d/%d/%d" % (nd, nf, nt)

    VDIR_STATS = ("n_files", "n_dirs", "n_total",)

    def __iter_stat__(self):
        return iter(self.VDIR_STATS)

    def __contains_stat__(self, name):
        return name in self.VDIR_STATS

    def __get_stat__(self, name):
        if name == "n_total":
            return len(self._images)
        if name == "n_files":
            count = 0
            for i in self._images.values():
                count += not i.is_directory_like
            return count
        if name == "n_dirs":
            count = 0
            for i in self._images.values():
                count += i.is_directory_like
            return count
        raise ValueError(name)


class Merged(Image):

    def __init__(self, *images):
        self._merged = set(images)

    def merge(self, image):
        self._merged.add(image)

    def __iter__(self):
        return iter(self._merged)

    def observe(self, *a):
        for image in self._merged:
            image.observe(*a)

    def forget(self, *a):
        for image in self._merged:
            image.forget(*a)

    MERGED_VIEWS = set([
        SubimageProvider,
        StatView,
        SummaryView,
        BackupStatView,
    ])

    def iter_available_views(self):
        common = common_supers(*(i.__views__ for i in self._merged))
        for v in common & self.MERGED_VIEWS:
            yield v
        if len(self._merged) > 1:
            yield BackupView

    @property
    def __views__(self):
        return tuple(self.iter_available_views())

    def __iter_backup__(self):
        is_directory_like = None
        names = set()
        for i in self:
            try:
                v = i.view(SubimageProvider)
            except NotImplemented:
                if is_directory_like is None:
                    is_directory_like = False
                elif is_directory_like:
                    # different kind of items
                    return iter(())
            else:
                if is_directory_like is None:
                    is_directory_like = True
                elif not is_directory_like:
                    # different kind of items
                    return iter(())
            names.update(v)
        return iter(names)

    def __contains_backup__(self, name):
        for n in self.__iter_backup__():
            if n == name:
                return True
        return False

    def __get_backup__(self, name):
        variants = []
        eq = 0
        for i in self:
            v = i.view(SubimageProvider)
            if name in v:
                item = v[name]
            else:
                continue
            try:
                isv = item.view(BackupStatView)
            except NotImplementedError:
                isv = None
            for visv in variants:
                if visv is None:
                    if isv is None:
                        eq += 1
                        break
                else:
                    if isv is None:
                        continue
                if visv.equals_to(isv):
                    eq += 1
                    break
            else:
                variants.append(isv)

        if eq:
            if len(variants) == 1:
                return BackupView.EQUAL
            else:
                return BackupView.DIFFERENT
        else:
            if len(variants) == 1:
                return BackupView.UNIQUE
            else:
                return BackupView.DIFFERENT

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

    def iter_cmp_stat(self, name):
        prev = object()  # anything that cannot match first v
        for v in self.iter_views_values(name, StatView):
            if v == prev:
                yield "="
            else:
                yield v
                prev = v

    def __get_stat__(self, name):
        return tuple(self.iter_cmp_stat(name))

    def __summary_str__(self):
        parts = []
        part = parts.append
        for v in self.iter_views(SummaryView):
            if v is None:
                part("-")
            else:
                s = str(v)
                if parts and parts[-1] == s:
                    part ("=")
                else:
                    part(s)
        return " | ".join(parts)

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


_fsc_empty_dict = {}


class OSFileSystem:

    def isdir(self, path):
        return self.get(path, isdir)

    def isfile(self, path):
        return self.get(path, isfile)

    def listdir(self, path):
        return self.get(path, listdir)

    def stat(self, path):
        return self.get(path, stat)


class FileSystemTTLCache(OSFileSystem):

    def __init__(self, ttl = 10.):
        self._tree = {}
        self.ttl = ttl
        self.last_drop = time()

    def get(self, path, getter):
        global _fsc_empty_dict
        node = self._tree
        for name in split(path):
            node = node.setdefault(name, _fsc_empty_dict)
            if node is _fsc_empty_dict:
                _fsc_empty_dict = {}
        t = time()
        try:
            data, ts = node[getter]
            if t - ts < self.ttl:
                return data
        except KeyError:
            pass

        data = getter(path)
        node[getter] = data, t
        return data

    def co_drop(self):
        t = time()
        ttl = self.ttl

        print("dropping...")

        tree = self._tree

        stack = [(_fsc_drop_visit, tree, t, ttl, *nc) for nc in tree.items()]
        pop = stack.pop
        extend = stack.extend

        while stack:
            stage, *args = pop()
            yield True
            extend(stage(*args))

        print("dropping took %f s" % (time() - t))

        self.last_drop = t


class FileSystemCache(OSFileSystem):

    def __init__(self, threshold = 100000):
        self._tree = {}
        self._threshold = threshold
        self._n = 0

    def get(self, path, getter):
        global _fsc_empty_dict
        node = self._tree
        for name in split(path):
            node = node.setdefault(name, _fsc_empty_dict)
            if node is _fsc_empty_dict:
                _fsc_empty_dict = {}
        try:
            return node[getter]
        except KeyError:
            pass

        data = node.get(getter)
        if data is None:
            data = getter(path)
            node[getter] = data
            self._n += 1
        return data

    def co_drop(self):
        if self._n < self._threshold:
            return
        yield
        self._tree.clear()
        self._n = 0


def _fsc_drop_leave(parent, name, node):
    if not node:
        del parent[name]
    return
    yield  # to be a generator


def _fsc_drop_visit(parent, t, ttl, name, node):
    if isinstance(node, dict):
        yield _fsc_drop_leave, parent, name, node
        for nc in node.items():
            yield _fsc_drop_visit, node, t, ttl, *nc
    else:
        __, ts = node
        if t - ts > ttl:
            del parent[name]


class FSNode(Image):

    n_inner_files = None
    n_inner_dirs = None

    fs = FileSystemCache()

    def __init__(self, name, parent = None, fs = None):
        self._name = name
        self._parent = parent
        self._cache = {}
        if fs is not None and fs is not self.fs:
            self.fs = fs

    def iter_reversed_path(self):
        n = self
        while n is not None:
            yield n._name
            n = n._parent

    @property
    def path(self, _cache = dict()):
        path = _cache.get(self)
        if path is None:
            path = join(*reversed(tuple(self.iter_reversed_path())))
            if len(_cache) > 10000:
                _cache.clear()
            _cache[self] = path
        return path

    @property
    def __views__(self):
        return tuple(self.iter_views())

    def iter_views(self):
        if self.fs.isdir(self.path):
            yield SubimageProvider
        yield StatView
        yield BackupStatView
        yield SummaryView

    def __iter_names__(self):
        try:
            return iter(self.fs.listdir(self.path))
        except PermissionError:
            return iter(())

    def __contains_subimage__(self, name):
        try:
            return name in self.fs.listdir(self.path)
        except PermissionError:
            return None

    def __get_subimage__(self, name):
        cache = self._cache
        fs = self.fs
        ret = cache.get(name)
        path = self.path
        if ret is None:
            subpath = join(path, name)
            if (
                exists(subpath)
                # Broken symlinks are present in `listdir` but `not exists`.
             or name in fs.listdir(path)
            ):
                ret = FSNode(name, parent = self, fs = fs)
                cache[name] = ret
            else:
                raise KeyError(name)
        return ret

    DIR_AUTO_STATS = (
        "n_files",
        "n_dirs",
        "n_total",
        "n_inner_files",
        "n_inner_dirs",
    )

    def __iter_stat__(self):
        path = self.path
        fs = self.fs

        if fs.isfile(path):
            return (n for n in dir(stat(path)) if n.startswith("st_"))

        if fs.isdir(path):
            return chain(
                (n for n in dir(stat(path)) if n.startswith("st_")),
                self.DIR_AUTO_STATS
            )

    FILE_BACKUP_STATS = frozenset([
        "st_mtime",
        "st_size",
    ])
    DIR_BACKUP_STATS = frozenset(DIR_AUTO_STATS)

    def __iter_backup_stat__(self):
        path = self.path

        if self.fs.isdir(path):
            return iter(self.DIR_BACKUP_STATS)
        else:
            return iter(self.FILE_BACKUP_STATS)

    def __contains_stat__(self, name):
        path = self.path
        fs = self.fs

        if fs.isfile(path):
            return hasattr(stat(path), name)

        if fs.isdir(path):
            return (name in self.DIR_AUTO_STATS) \
                or hasattr(stat(path), name)

    @property
    def n_dirs(self):
        isdir = self.fs.isdir
        path = self.path
        count = 0
        for n in self.__iter_names__():
            count += isdir(join(path, n))
        return count

    @property
    def n_files(self):
        isfile = self.fs.isfile
        path = self.path
        count = 0
        for n in self.__iter_names__():
            count += isfile(join(path, n))
        return count

    @property
    def n_total(self):
        return len(tuple(self.__iter_names__()))

    def __get_stat__(self, name):
        path = self.path
        fs = self.fs

        if fs.isfile(path):
            return getattr(stat(path), name)

        if fs.isdir(path):
            if name in self.DIR_AUTO_STATS:
                return getattr(self, name)
            return getattr(stat(path), name)

    BYTE_MULTS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB")

    def __summary_str__(self):
        path = self.path
        fs = self.fs
        isfile = fs.isfile
        isdir = fs.isdir

        if isfile(path):
            st = fs.stat(path)
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

            return "D %d/%d/%d %s/%s" % (nd, nf, nt,
                "?" if self.n_inner_dirs is None else str(self.n_inner_dirs),
                "?" if self.n_inner_files is None
                    else str(self.n_inner_files),
            )

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

    __side__ = 0

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


class TkImageViewWidget(ImageViewWidget):

    def __image_changed__(self, __):
        self.forget()
        self.invalidate_image()

    def observe(self, *events):
        self._image.observe(self.__observe__, *events)

    def forget(self, *events):
        self._image.forget(self.__observe__, *events)

    def __observe__(self, **__):
        self.invalidate_image()

    def invalidate_image(self):
        self.show_image = -100

    @tk_delayed
    def show_image(self):
        self.__show_image__()
        self.observe()


class StatFrame(GUIFrame, TkImageViewWidget):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)

        GUIFrame.__init__(self, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self._tv = tv = Treeview(self,
            show = "tree",
        )
        self._tv_cache = []  # of detached items
        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv, sizegrip = sizegrip)

    def __show_image__(self):
        image = self.image
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
                values = tuple(("-" if n is None else n) for n in val),
            )

            tv.item(ciid, **cfg)

ImageViewWidget.__view2widget__[StatView] = StatFrame


class SubimagesFrame(GUIFrame, TkImageViewWidget):

    __side__ = -1 # to the left

    icons = Pictures(
        subtree = pic_path("subtree.png"),
        opaque  = pic_path("opaque.png"),
    )

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)

        GUIFrame.__init__(self, *a, **kw)

        self.rowconfigure(0, weight = 1)
        self.columnconfigure(0, weight = 1)

        self._tv = tv = Treeview(self,
            selectmode = BROWSE,
            columns = ["summary"],
        )
        tv.heading("#0", text = "Name")
        tv.heading("summary", text = "Summary")
        self._tv_cache = []  # of detached items
        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(self, tv, sizegrip = sizegrip)

        tv.bind("<Double-Button-1>", self._on_tv_2b1)
        tv.bind("<Return>", self._on_tv_enter)

        tv.tag_configure(BackupView.EQUAL, background = "#AAFFAA")
        tv.tag_configure(BackupView.DIFFERENT, background = "#FFCCAA")
        tv.tag_configure(BackupView.UNIQUE, background = "#FFAAAA")

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

    def __show_image__(self):
        image = self.image
        tv = self._tv
        tv_cache = self._tv_cache
        ico_subtree = self.icons.subtree
        ico_opaque = self.icons.opaque

        sp = SubimageProvider(image)

        try:
            mv = image.view(BackupView)
        except NotImplementedError:
            mv = None

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
                values = ["?"],
                tags = [],
            )

            subimg = sp[name]

            if subimg.is_directory_like:
                cfg["image"] = ico_subtree
            else:
                cfg["image"] = ico_opaque

            try:
                sv = subimg.view(SummaryView)
            except NotImplementedError:
                pass
            else:
                cfg["values"][0] = str(sv)

            if mv is not None:
                cfg["tags"].append(mv[name])

            tv.item(ciid, **cfg)

            subimg.observe(self.__observe__)

ImageViewWidget.__view2widget__[SubimageProvider] = SubimagesFrame


class ImgviewFrame(GUIFrame):

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        self._cv = cv = Chainview(self)
        cv.bind(Chainview.EVENT_SELECT, self._on_chainview_select, "+")
        cv.pack(fill = X)

        self._apw_img_widgets = apw = AutoPanedWindow(self)
        apw.pack(fill = BOTH, expand = True)

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
        self._cv.chain = ()
        self._refresh_img_w()

    def _on_chainview_select(self, e):
        self._refresh_img_w()

    def _refresh_img_w(self):
        img = self.tree
        for name in self._cv.subchain:
            img = SubimageProvider(img)[name]

        apw = self._apw_img_widgets
        unused = set(apw.winfo_children())

        if img is not None:
            WCls2w = dict((type(w), w) for w in unused)

            available_views = sorted(
                tuple(map(
                    ImageViewWidget.__view2widget__.get,
                    common_supers(
                        img.__views__,
                        ImageViewWidget.__view2widget__,
                    )
                )),
                key = lambda cls : (
                    cls.__side__,
                    cls.__name__,
                ),
            )
            for WCls in available_views:
                img_w = WCls2w.pop(WCls, None)

                if img_w is None:
                    img_w = self._img_w_cache.pop(WCls, None)
                else:
                    unused.remove(img_w)

                if img_w is None:
                    img_w = WCls(apw)
                    img_w.bind(
                        img_w.EVENT_ENTER_SUBIMAGE,
                        self._on_enter_subimage
                    )

                apw.add(img_w)
                img_w.image = img

        for img_w in unused:
            assert img_w is self._img_w_cache.setdefault(
                type(img_w), img_w
            )
            apw.remove(img_w)

    def _on_enter_subimage(self, e):
        siname = e.widget.subimage_name
        cv = self._cv
        cv.chain = cv.subchain + (siname,)
        cv.index = -1


class ImgviewTk(GUITk):

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)
        self.title("Image view")
        self._apw = apw = AutoPanedWindow(self, orient = VERTICAL)
        apw.pack(fill = BOTH, expand = True)
        self._f_imgs = f = ImgviewFrame(apw)
        apw.add(f)
        self._f_tasks = f = TasksFrame(apw, sizegrip = True)
        apw.add(f)
        f.start_periodic_update(self.task_manager)

    @property
    def tree(self):
        return self._f_imgs.tree

    @tree.setter
    def tree(self, tree):
        self._f_imgs.tree = tree


def co_fs_node_analyzer(tree):
    t0 = time()
    stack = [(_co_fs_node_visit, tree)]
    pop = stack.pop
    extend = stack.extend
    while stack:
        phase, node = pop()
        yield True
        extend(phase(node))
    t1 = time()
    print("file system analysis took %f s" % (t1 - t0))


def _co_fs_node_visit(img):
    if img.is_directory_like:
        sp = img.view(SubimageProvider)
        yield (_co_fs_node_leave, sp)
        for name in sp:
            si = sp[name]
            yield (_co_fs_node_visit, si)


def _co_fs_node_leave(sp):
    n_dirs = 0
    n_files = 0

    for name in sp:
        si = sp[name]
        if si.is_directory_like:
            n_dirs += si.n_inner_dirs + si.n_dirs
            n_files += si.n_inner_files + si.n_files

    img = sp._image
    img.n_inner_dirs = n_dirs
    img.n_inner_files = n_files

    obs(img, "n_inner")

    return
    yield


def fs_node_analyzer(tree):
    t0 = time()
    stack = [(_co_fs_node_visit, tree)]
    pop = stack.pop
    extend = stack.extend
    while stack:
        phase, node = pop()
        extend(phase(node))
    t1 = time()
    print("file system analysis took %f s" % (t1 - t0))


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("path",
        nargs = "+",
        help = "v/path os/path"
    )

    args = ap.parse_args()

    tracemalloc.start()

    vroot = VirtualDirectory()

    paths = args.path
    if len(paths) & 1:
        raise ValueError("paths must be paired, 'virtual path' 'OS path'")

    os_nodes = []

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
        os_nodes.append(os_node)
        if isinstance(d, VirtualDirectory):
            d._parent.override(n, Merged(d, os_node))
        else:
            d.merge(os_node)

    root = ImgviewTk()
    root.tree = vroot
    for os_node in os_nodes:
        root.enqueue(co_fs_node_analyzer(os_node))

    def co_drop():
        yield FSNode.fs.co_drop()
        root.after(1000, drop_fs_cache)

    def drop_fs_cache():
        root.enqueue(co_drop())

    drop_fs_cache()

    root.mainloop()

    sn = tracemalloc.take_snapshot()
    display_top(sn)


def display_top(snapshot, key_type  = "lineno", limit = 10):
    snapshot = snapshot.filter_traces((
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
        tracemalloc.Filter(False, "<unknown>"),
    ))
    top_stats = snapshot.statistics(key_type)

    print("Top %s lines" % limit)
    for index, stat in enumerate(top_stats[:limit], 1):
        frame = stat.traceback[0]
        # replace "/path/to/module/file.py" with "module/file.py"
        filename = join(*split(frame.filename)[-2:])
        print("#%s: %s:%s: %.1f KiB"
              % (index, filename, frame.lineno, stat.size / 1024))
        line = linecache.getline(frame.filename, frame.lineno).strip()
        if line:
            print('    %s' % line)

    other = top_stats[limit:]
    if other:
        size = sum(stat.size for stat in other)
        print("%s other: %.1f KiB" % (len(other), size / 1024))
    total = sum(stat.size for stat in top_stats)
    print("Total allocated size: %.1f KiB" % (total / 1024))


if __name__ == "__main__":
    exit(main() or 0)
