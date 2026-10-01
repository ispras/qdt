__all__ = [
    "PatchEditorFrame"
]

from .auto_paned import (
    AutoPanedWindow,
)
from .gui_frame import (
    GUIFrame,
)
from .gui_text import (
    GUIText,
    READONLY,
)
from .scrollframe import (
    add_scrollbars_native,
)
from .var_widgets import (
    VarTreeview,
)

from common import (
    mlget as _,
    pypath,
)

from six.moves.tkinter import (
    BOTH,
    BROWSE,
    END,
    HORIZONTAL,
    NONE,
    RAISED,
)
with pypath("..unidiff"):
    from unidiff import (
        PatchSet,
        LINE_TYPE_ADDED,
        LINE_TYPE_REMOVED,
    )
    from unidiff.constants import (
        LINE_TYPE_NO_NEWLINE,
    )


TAG_ADDED = "a"
TAG_REMOVED = "r"
TAG_MODIFIED = "!"
TAG_HEADING = "@"
TAG_NO_NEWLINE = "\\"

line_type_to_tag = {
    LINE_TYPE_ADDED: TAG_ADDED,
    LINE_TYPE_REMOVED: TAG_REMOVED,
    LINE_TYPE_NO_NEWLINE: TAG_NO_NEWLINE
}


class PatchEditorFrame(
    GUIFrame,
    object # for `property` (Py2)
):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)

        # properties
        self._patch_file_name = None
        self._patch_set = None

        GUIFrame.__init__(self, *a, **kw)

        self._ap = autopaned = AutoPanedWindow(self,
            sashrelief = RAISED,
            orient = HORIZONTAL
        )
        autopaned.pack(fill = BOTH, expand = True)

        # file tree
        fr = GUIFrame(autopaned)
        autopaned.add(fr, sticky = "NESW")

        fr.rowconfigure(0, weight = 1)
        fr.columnconfigure(0, weight = 1)

        self._tv_files = tv = VarTreeview(fr,
            selectmode = BROWSE
        )

        add_scrollbars_native(fr, tv)

        tv.grid(row = 0, column = 0, sticky = "NESW")

        tv.heading("#0", text = _("Files"))

        tv.tag_configure(TAG_ADDED, background = "#DDFFDD")
        tv.tag_configure(TAG_REMOVED, background = "#FFDDDD")
        tv.tag_configure(TAG_MODIFIED, background = "#FFFFDD")

        tv.bind("<<TreeviewSelect>>", self._on_tv_files_select, "+")
        self.current_file = None
        self.current_dir = None

        # file view
        fr = GUIFrame(autopaned)
        autopaned.add(fr, sticky = "NESW")

        fr.rowconfigure(0, weight = 1)
        fr.columnconfigure(0, weight = 1)
        self._t_file = t = GUIText(fr,
            state = READONLY,
            wrap = NONE
        )

        t.tag_configure(TAG_ADDED, background = "#DDFFDD")
        t.tag_configure(TAG_REMOVED, background = "#FFDDDD")
        t.tag_configure(TAG_HEADING, background = "#DDDDFF")
        t.tag_configure(TAG_NO_NEWLINE,
            background = "#AA0000",
            foreground = "#FFFFFF"
        )

        # do not overcome "sel"ection tag
        for tag in (TAG_ADDED, TAG_REMOVED, TAG_HEADING, TAG_NO_NEWLINE):
            t.tag_lower(tag)

        add_scrollbars_native(fr, t, sizegrip = sizegrip)

        t.grid(row = 0, column = 0, sticky = "NESW")

        tv.bind("<Button-3>", self._on_tv_files_b3, "+")
        self.current_hunk = None

        t.bind("<Button-3>", self._on_t_file_b3, "+")

        # delayed file selection (if treeview is being constructed)
        self._do_select_file = None

    def iter_current_directory(self):
        tv = self._tv_files
        for dir_id in tv.selection():
            i = int(tv.item(dir_id, "tags")[1])
            if i >= 0: # it's a file
                dir_id = tv.parent(dir_id)
            # only one
            break
        else: # nothing selected
            return

        queue = [dir_id]

        while queue:
            iid = queue.pop(0)

            i = int(tv.item(iid, "tags")[1])

            if i < 0: # directory
                queue = list(tv.get_children(iid)) + queue
                continue

            # file
            yield i

    def _on_t_file_b3(self, e):
        tags = self._t_file.tag_names("@%d,%d" % (e.x, e.y))

        for t in tags:
            try:
                hunk_idx = int(t)
                break
            except ValueError:
                continue
        else:
            return
        self.current_hunk = hunk_idx
        self.event_generate("<<Button-3-Hunk>>")

    @property
    def patch_file_name(self):
        return self._patch_file_name

    @patch_file_name.setter
    def patch_file_name(self, patch_file_name):
        self.__patch_set = None

        self._patch_file_name = patch_file_name
        if patch_file_name is not None:
            self.__patch_set = PatchSet.from_filename(self._patch_file_name)

    @property
    def __patch_set(self):
        return self._patch_set

    @__patch_set.setter
    def __patch_set(self, patch_set):
        if self._patch_set is not None:
            self._cleanup()
        self._patch_set = patch_set
        if patch_set is not None:
            self._read_patch()

    @property
    def patch_set(self):
        return self.__patch_set

    @patch_set.setter
    def patch_set(self, patch_set):
        # patch set is set directly, current patch_file_name does not
        # correspond to it likely.
        self.patch_file_name = None
        self.__patch_set = patch_set

    def _read_patch(self):
        # TODO: in main window
        # self.title(_("%s - %s") % (_("Patch Editor"), self._patch_file_name))
        self._reading_task = task = self._co_read_patch()
        self.enqueue(task)

    def _cleanup(self):
        try:
            task = self._reading_task
        except AttributeError:
            pass
        else:
            del self._reading_task
            self.cancel_task(task)

        self._tv_files.delete(*self._tv_files.get_children())
        self._t_file.delete("1.0", END)
        self._do_select_file = None

    def _co_read_patch(self):
        patch = self._patch_set

        yield True
        # Preserve original indices before sorting.
        sorted_patch = sorted(((f, i) for (i, f) in enumerate(patch)),
            key = lambda fi : fi[0].path.lower()
        )

        yield True

        tv = self._tv_files
        insert = tv.insert
        exists = tv.exists
        item = tv.item

        yield True

        for f, f_idx in sorted_patch: # it's a `list`
            yield True

            if f.is_added_file:
                tag = TAG_ADDED
            elif f.is_removed_file:
                tag = TAG_REMOVED
            else:
                tag = TAG_MODIFIED

            f_path_t = f.path.split("/")

            for i in range(len(f_path_t) - 1, -1, -1):
                parent = "/".join(f_path_t[:i])
                if exists(parent):
                    break

            prev_parent = "/".join(f_path_t[:i])

            for i in range(i + 1, len(f_path_t) + 1):
                parent = "/".join(f_path_t[:i])
                assert parent == insert(prev_parent, END, parent,
                    text = f_path_t[i - 1],
                    open = True,
                    tags = ["", "-1", f_path_t[:i]]
                )
                prev_parent = parent

            item(prev_parent, tags = [tag, f_idx])

        yield True
        del self._reading_task

        if self._do_select_file is not None:
            self.select_file(self._do_select_file)
            self._do_select_file = None

    def _on_tv_files_select(self, __):
        tv = self._tv_files
        for _id in tv.selection():
            i = int(tv.item(_id, "tags")[1])
            if i < 0:
                # directory
                break
            self.current_file = i
            self._set_patched_file(self._patch_set[i])
            # only one
            break

    def _on_tv_files_b3(self, e):
        tv = self._tv_files

        _id = tv.identify_row(e.y)

        if _id:
            tv.selection_set(_id)

            tags = tv.item(_id, "tags")
            i = int(tags[1])
            if i >= 0:
                self.event_generate("<<Button-3-File>>")
            else:
                self.current_dir = tags[2]
                self.event_generate("<<Button-3-Dir>>")

    def select_file(self, i):
        if hasattr(self, "_reading_task"):
            self._do_select_file = i
            return

        tv = self._tv_files
        file = self._patch_set[i]
        tv.selection_set(file.path)

    def _set_patched_file(self, pf):
        t = self._t_file
        t.delete("1.0", END)

        insert = t.insert

        for i, hunk in enumerate(pf):
            # like first part of Hunk.__str__
            head = "@@ -%d,%d +%d,%d @@%s\n" % (
                hunk.source_start, hunk.source_length,
                hunk.target_start, hunk.target_length,
                " " + hunk.section_header if hunk.section_header else ""
            )

            insert(END, head, [i, TAG_HEADING])

            for line in hunk:
                tags = [i]

                tag = line_type_to_tag.get(line.line_type, None)
                if tag is not None:
                    tags.append(tag)

                insert(END, line.value, tags)
