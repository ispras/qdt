from argparse import (
    ArgumentParser,
)
from common import (
    mlget as _,
    pypath,
    gen_similar_file_name,
)
with pypath("..unidiff"):
    from unidiff import (
        PatchSet,
        PatchedFile,
    )
from widgets import (
    GUITk,
    VarTreeview,
    add_scrollbars_native,
    GUIText,
    AutoPanedWindow,
    GUIFrame,
    VarMenu,
    TkPopupHelper,
    asksaveas,
    askyesno,
    ErrorDialog,
    VarButton,
    askopen,
    VarLabel,
    HKEntry,
    StringVar,
    LineSelectDialog,
    PatchEditorFrame,
)
from os import (
    listdir,
)
from os.path import (
    isdir,
    join,
)
from six.moves.tkinter import (
    END,
    BROWSE,
    RAISED,
    BOTH,
    NONE,
    VERTICAL,
    RIGHT,
)
from traceback import (
    format_exc,
)
from datetime import (
    datetime,
)
from dateutil.tz import (
    tzlocal,
)


class CommitInfo(object):

    def __init__(self,
        prefix = [],
        author = "",
        date = "",
        message = "",
        last_parsed_line = None
    ):
        self.prefix = prefix
        self.author = author
        self.date = date
        self.message = message
        self.last_parsed_line = last_parsed_line

    def __str__(self):
        return "".join(self.as_lines)

    @property
    def as_lines(self):
        msg_lines = self.message.splitlines(True)
        ret = [
            "From: " + self.author + "\n",
            "Date: " + self.date + "\n",
            "Subject: " + msg_lines[0]
        ] + msg_lines[1:]

        if self.prefix:
            ret = self.prefix + ret
        return ret

    @staticmethod
    def parse(lines):
        # According to git-am manual page "DISCUSSION" section.
        prefix = []
        author = None
        date = None
        message = None

        liter = iter(enumerate(lines))

        for __, l in liter:
            if l.startswith("From:"):
                author = l[5:].strip()
                break
            elif l.startswith("Date:"):
                date = l[5:].strip()
                break
            else:
                prefix.append(l)

        for i, l in liter:
            if l.startswith("From:"):
                if author is not None:
                    raise Exception("Double From:")
                author = l[5:].strip()
            elif l.startswith("Date:"):
                if date is not None:
                    raise Exception("Double Date:")
                date = l[5:].strip()
            elif l.startswith("Subject:"):
                message = l[8:].lstrip() or l[-1] # empty
                break
            else:
                # prefix is not allowed
                raise Exception("Unexpected line " + l)

        for i, l in liter:
            # don't strip each line, suspected only
            if l.startswith("---") and l.strip() == "---" \
            or l.startswith("diff -") \
            or l.startswith("Index: "):
                i -= 1
                break
            message += l

        if author is None:
            raise Exception("No From:")
        if date is None:
            raise Exception("No Date:")
        if message is None:
            raise Exception("No Subject:")

        return CommitInfo(
            author = author,
            date = date,
            message = message,
            prefix = prefix,
            last_parsed_line = i
        )


def remove_file_from_patch(patch, file_idx):
    f = patch.pop(file_idx)

    # First file may has commit info in patch info.
    # Move it to next file (now first).
    # TODO: now if patch becomes empty, commit info is lost.
    if file_idx == 0:
        try:
            ci = CommitInfo.parse(f.patch_info)
        except:
            pass
        else:
            ci_limit = ci.last_parsed_line + 1
            pi_lines = f.patch_info[0:ci_limit]
            del f.patch_info[0:ci_limit]

            if patch:
                patch[0].patch_info[:0] = pi_lines

    return f


def merge_hunks(dst, src):
    # TODO: check for possible overlapping

    siter = iter(src)
    i = 0
    for shunk in siter:
        while True:
            try:
                dhunk = dst[i]
            except IndexError:
                # just append the rest
                dst.extend(siter)
                return

            if shunk.source_start < dhunk.source_start:
                dst.insert(i, shunk)
                i += 1
                break
            else:
                i += 1


class CommitEditorFrame(
    GUIFrame,
    object # for `property` (Py2)
):

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        self.columnconfigure(0, weight = 0)
        self.columnconfigure(1, weight = 1)
        self.columnconfigure(2, weight = 0)

        row = 0

        self.rowconfigure(row, weight = 0)
        VarLabel(self,
            text = _("Author (From:)")
        ).grid(
            row = row,
            column = 0,
            sticky = "NES"
        )
        self._v_from = v = StringVar(self)
        HKEntry(self,
            textvariable = v
        ).grid(
            row = row,
            column = 1,
            columnspan = 2,
            sticky = "NESW"
        )

        row += 1
        self.rowconfigure(row, weight = 0)
        VarLabel(self,
            text = _("Date:")
        ).grid(
            row = row,
            column = 0,
            sticky = "NES"
        )
        self._v_date = v = StringVar(self)
        HKEntry(self,
            textvariable = v
        ).grid(
            row = row,
            column = 1,
            sticky = "NESW"
        )
        VarButton(self,
            text = _("Now"),
            command = self._on_now
        ).grid(
            row = row,
            column = 2,
            sticky = "NESW"
        )

        row += 1
        self.rowconfigure(row, weight = 0)
        VarLabel(self,
            text = _("First line (Subject:)")
        ).grid(
            row = row,
            column = 0,
            sticky = "NES"
        )
        self._v_subject = v = StringVar(self)
        HKEntry(self,
            textvariable = v
        ).grid(
            row = row,
            column = 1,
            columnspan = 2,
            sticky = "NESW"
        )

        row += 1
        self.rowconfigure(row, weight = 0)
        VarLabel(self,
            text = _("Commit message (2-nd and rest lines)")
        ).grid(
            row = row,
            column = 0,
            columnspan = 3,
            sticky = "NESW"
        )

        row += 1
        self.rowconfigure(row, weight = 1)

        fr = GUIFrame(self)
        fr.columnconfigure(0, weight = 1)
        fr.rowconfigure(0, weight = 1)
        fr.grid(
            row = row,
            column = 0,
            columnspan = 3,
            sticky = "NESW"
        )

        self._t_commit_message = t = GUIText(fr,
            wrap = NONE
        )
        t.grid(
            row = 0,
            column = 0,
            sticky = "NESW"
        )
        add_scrollbars_native(fr, t)

        row += 1
        self.rowconfigure(row, weight = 0)

        fr = GUIFrame(self)
        fr.grid(
            row = row,
            column = 0,
            columnspan = 3,
            sticky = "NESW"
        )

        VarButton(fr,
            text = _("Revert"),
            command = self._on_revert
        ).pack(
            side = RIGHT
        )
        VarButton(fr,
            text = _("Apply"),
            command = self._on_apply
        ).pack(
            side = RIGHT
        )

        self.commit_info = None

    def _on_now(self):
        dt = datetime.now(tzlocal())
        self._v_date.set(dt.strftime("%a, %d %b %Y %H:%M:%S %z"))

    def _on_revert(self):
        commit_info = self._commit_info
        self._t_commit_message.delete("1.0", END)
        if commit_info is None:
            self._v_from.set("")
            self._v_date.set("")
            self._v_subject.set("")
        else:
            self._v_from.set(commit_info.author)
            self._v_date.set(commit_info.date)

            subject, message = commit_info.message.split("\n", 1)

            self._v_subject.set(subject)
            self._t_commit_message.insert(END, message)

    def _on_apply(self):
        commit_info = self._commit_info
        if commit_info is None:
            self._commit_info = commit_info = CommitInfo()
        commit_info.author = self._v_from.get()
        commit_info.date = self._v_date.get()

        commit_message = self._t_commit_message.get("1.0", "end-1c")
        commit_info.message = self._v_subject.get() + "\n" + commit_message

        self.event_generate("<<Applied>>")

    @property
    def commit_info(self):
        return self._commit_info

    @commit_info.setter
    def commit_info(self, commit_info):
        self._commit_info = commit_info
        self._on_revert()


class PatchSeriesEditorFrame(
    GUIFrame,
    TkPopupHelper,
    object # for `property` (Py2)
):

    def __init__(self, *a, **kw):
        sizegrip = kw.pop("sizegrip", False)

        # properties
        self._patch_file_names = None

        GUIFrame.__init__(self, *a, **kw)
        TkPopupHelper.__init__(self)

        self._ap = autopaned = AutoPanedWindow(self,
            sashrelief = RAISED,
            orient = VERTICAL
        )
        autopaned.pack(fill = BOTH, expand = True)

        # patch series
        fr = GUIFrame(autopaned)
        autopaned.add(fr, sticky = "NESW")

        fr.columnconfigure(0, weight = 1)
        fr.rowconfigure(0, weight = 1)

        self._tv_patches = tv = VarTreeview(fr,
            selectmode = BROWSE,
            columns = ["changed"]
        )
        tv.grid(row = 0, column = 0, sticky = "NESW")

        add_scrollbars_native(fr, tv)

        tv.heading("#0", text = _("Patches"))
        tv.heading("changed", text = _("Changed"))
        tv.column("changed", width = 100, stretch = False)

        tv.bind("<<TreeviewSelect>>", self._on_tv_patches_select, "+")
        tv.bind("<Double-Button-1>", self._on_tv_patches_double_b1, "+")
        tv.bind("<Button-3>", self._on_tv_patches_button_3, "+")

        # patch series popup
        self._patch_series_popup = menu = VarMenu(self, tearoff = False)
        menu.add("command",
            label = _("Save"),
            command = self._on_save_patch
        )
        menu.add("command",
            label = _("Reload"),
            command = self._on_reload_patch
        )
        menu.add("command",
            label = _("Rename"),
            command = self._on_rename_patch
        )
        menu.add("command",
            label = _("Add above"),
            command = self._on_add_patch_above
        )
        menu.add("command",
            label = _("Add below"),
            command = self._on_add_patch_below
        )
        menu.add("command",
            label = _("Load above"),
            command = self._on_load_patch_above
        )
        menu.add("command",
            label = _("Load below"),
            command = self._on_load_patch_below
        )
        menu.add("command",
            label = _("Forget"),
            command = self._on_forget_patch
        )

        # empty space popup
        self._empty_space_popup = menu = VarMenu(self, tearoff = False)
        menu.add("command",
            label = _("Load"),
            command = self._on_load_patch
        )

        # commit editing
        self._cef = cef = CommitEditorFrame(autopaned)
        autopaned.add(cef, sticky = "NESW")

        cef.bind("<<Applied>>", self._on_commit_info_applied)

        # patch editor
        self._pef = pef = PatchEditorFrame(autopaned,
            sizegrip = sizegrip
        )
        autopaned.add(pef, sticky = "NESW")

        pef.bind("<<MoveHunkTo>>", self._on_move_hunk_to)
        pef.bind("<<MoveFileTo>>", self._on_move_file_to)
        pef.bind("<<MoveDirTo>>", self._on_move_dir_to)

    def _ask_for_target(self):
        move_targets = list(self.patch_names)

        if len(move_targets) == 1:
            # only one patch
            return

        tv = self._tv_patches

        for _id in tv.selection():
            move_targets.remove(tv.item(_id, "text"))
            break # only one

        lsd = LineSelectDialog(lines = move_targets)
        lsd.title(_("Select target patch"))

        target_idx = lsd.wait()
        if target_idx is None:
            return

        target_name = move_targets[target_idx]

        for _id in tv.get_children():
            if tv.item(_id, "text") == target_name:
                return _id

    def _on_move_hunk_to(self, __):
        dst_patch_id = self._ask_for_target()
        if dst_patch_id is None:
            return

        dst_patch_idx = self.get_patch_set_index(dst_patch_id)

        pef = self._pef
        hunk_idx = pef.current_hunk
        file_idx = pef.current_file
        tv = self._tv_patches

        for _id in tv.selection():
            src_patch_idx = self.get_patch_set_index(_id)
            src_patch_id = _id
            break # only one

        dst_patch = self._patch_sets[dst_patch_idx]
        src_patch = self._patch_sets[src_patch_idx]

        src_file = src_patch[file_idx]
        for dst_file in dst_patch:
            if dst_file.path == src_file.path:
                # TODO: check rest attributes
                break
        else:
            dst_file = PatchedFile(
                patch_info = src_file.patch_info,
                source = src_file.source_file,
                target = src_file.target_file,
                source_timestamp = src_file.source_timestamp,
                target_timestamp = src_file.target_timestamp,
                is_binary_file = src_file.is_binary_file,
                is_rename = src_file.is_rename
            )
            dst_patch.append(dst_file)

        hunk = src_file.pop(hunk_idx)
        if not src_file:
            remove_file_from_patch(src_patch, file_idx)

        # TODO: check for possible overlapping

        # preserve source file line order
        if dst_file:
            for i, h in enumerate(dst_file):
                if hunk.source_start < h.source_start:
                    dst_file.insert(i, hunk)
                    break
            else:
                dst_file.append(hunk)
        else:
            dst_file.append(hunk)

        # update
        pef.patch_set = src_patch

        # previous selection
        if src_file:
            pef.select_file(file_idx)

        # mark changed
        tv.item(src_patch_id, values = ["*"])
        tv.item(dst_patch_id, values = ["*"])

    def _on_move_file_to(self, __):
        dst_patch_id = self._ask_for_target()
        if dst_patch_id is None:
            return

        self._move_file_to(dst_patch_id, self._pef.current_file)

    def _move_file_to(self, dst_patch_id, file_idx):
        dst_patch_idx = self.get_patch_set_index(dst_patch_id)

        tv = self._tv_patches

        for _id in tv.selection():
            src_patch_idx = self.get_patch_set_index(_id)
            src_patch_id = _id
            break # only one

        dst_patch = self._patch_sets[dst_patch_idx]
        src_patch = self._patch_sets[src_patch_idx]

        src_file = remove_file_from_patch(src_patch, file_idx)

        for dst_file in dst_patch:
            if dst_file.path == src_file.path:
                # TODO: check rest attributes
                merge_hunks(dst_file, src_file)
                break
        else:
            # try to preserve order
            for i, dst_file in enumerate(dst_patch):
                if src_file.path < dst_file.path:
                    # move commit info to new first file
                    if i == 0:
                        try:
                            ci = CommitInfo.parse(dst_file.patch_info)
                        except:
                            pass
                        else:
                            ci_limit = ci.last_parsed_line + 1
                            ci_lines = dst_file.patch_info[0:ci_limit]
                            del dst_file.patch_info[0:ci_limit]
                            src_file.patch_info[:0] = ci_lines

                    dst_patch.insert(i, src_file)
                    break
            else:
                dst_patch.append(src_file)

        self._update_selected()

        # mark changed
        tv.item(src_patch_id, values = ["*"])
        tv.item(dst_patch_id, values = ["*"])

    def _on_move_dir_to(self, __):
        dst_patch_id = self._ask_for_target()
        if dst_patch_id is None:
            return

        # Use reverse order because of patches are `list`s and removing
        # less index results in invalidation of greater indices.
        to_move = list(sorted(self._pef.iter_current_directory(),
            reverse = True
        ))

        for file_idx in to_move:
            self._move_file_to(dst_patch_id, file_idx)

    @property
    def patch_file_names(self):
        return self._patch_file_names

    @patch_file_names.setter
    def patch_file_names(self, patch_file_names):
        if self._patch_file_names is not None:
            self._cleanup()

        if patch_file_names is None:
            self._patch_file_names = None
        else:
            # immutable and ordered
            self._patch_file_names = tuple(patch_file_names)
            self._read_patches()

    def _cleanup(self):
        try:
            task = self._filling_task
        except AttributeError:
            del self._patch_sets
        else:
            del self._filling_task
            self.cancel_task(task)

        self._tv_patches.delete(*self._tv_patches.get_children())

    def _read_patches(self):
        self._filling_task = task = self._co_fill_patches()
        self.enqueue(task)

    def iter_patch_file_names(self):
        queue = list(self._patch_file_names)
        pop, insert = queue.pop, queue.insert

        while queue:
            entry = pop(0)
            if isdir(entry):
                # 1. Use `reverse = True` because `insert(0, ...)` reverses
                #    order too.
                # 2. Don't use `os.walk` because alphabetical order is first.
                #    I.e. a directory is a split patch.
                for name in sorted(listdir(entry), reverse = True):
                    insert(0, join(entry, name))
            else:
                yield entry

    def _co_fill_patches(self):
        patch_sets = []

        tv = self._tv_patches
        insert = tv.insert

        errors = []

        for file_name in self.iter_patch_file_names():
            yield True
            try:
                patch_set = PatchSet.from_filename(file_name)
            except:
                errors.append(format_exc())
                continue

            yield True
            insert("", END, text = file_name, tags = [len(patch_sets)])

            patch_sets.append(patch_set)

        if errors:
            yield True
            ErrorDialog(
                summary = _("Errors during patch loading"),
                message = "\n\n".join(errors)
            ).wait()

        yield True
        del self._filling_task
        self._patch_sets = patch_sets

    def _on_tv_patches_select(self, __):
        self._update_selected()

    def _update_selected(self):
        tv = self._tv_patches
        for _id in tv.selection():
            patch_set_index = self.get_patch_set_index(_id)
            self._pef.patch_set = ps = self._patch_sets[patch_set_index]

            # first file in patch set may contain commit info
            try:
                file0 = ps[0]
            except IndexError:
                self._cef.commit_info = None
                break

            try:
                ci = CommitInfo.parse(file0.patch_info)
            except:
                self._cef.commit_info = None
            else:
                self._cef.commit_info = ci

            break # one or none
        else:
            self._pef.patch_file_name = None

    def _on_tv_patches_double_b1(self, *__):
        self._rename_selected()

    def _on_tv_patches_button_3(self, e):
        tv = self._tv_patches

        _id = tv.identify_row(e.y)
        if _id:
            tv.selection_set(_id)

            self.show_popup(e.x_root, e.y_root, self._patch_series_popup,
                tag = _id
            )
        else:
            self.show_popup(e.x_root, e.y_root, self._empty_space_popup,
                tag = None
            )

    def _on_save_patch(self):
        self.notify_popup_command()
        self.save_current()

    def save_current(self):
        tv = self._tv_patches

        for _id in tv.selection():
            file_name = tv.item(_id, "text")

            patch_set = self._patch_sets[self.get_patch_set_index(_id)]
            data = str(patch_set)

            try:
                with open(file_name, "w") as f:
                    f.write(data)
            except:
                ErrorDialog(
                    summary = _("Can't save %s") % file_name,
                    message = format_exc()
                ).wait()
            else:
                # not modified
                tv.item(_id, values = [""])

            break # one or none

    def _on_reload_patch(self):
        self.notify_popup_command()
        self.reload_current()

    def reload_current(self, confirm = True):
        tv = self._tv_patches
        for _id in tv.selection():
            file_name = tv.item(_id, "text")

            if confirm and not askyesno(self,
                title = _("Reload patch"),
                message = _("Patch %s will be reloaded. Continue?") % (
                    file_name
                )
            ):
                break

            try:
                patch_set = PatchSet.from_filename(file_name)
            except:
                ErrorDialog(
                    summary = _("Errors during patch loading"),
                    message = format_exc()
                ).wait()
                break

            idx = self.get_patch_set_index(_id)
            self._patch_sets[idx] = patch_set
            self._update_selected()

            # reset "changed" mark
            tv.item(_id, values = [""])

            break # one or none

    def _on_rename_patch(self):
        self.notify_popup_command()
        self._rename_selected()

    def _rename_selected(self):
        tv = self._tv_patches

        for _id in tv.selection():
            file_name = asksaveas(self,
                title = _("Set patch file name"),
                initial_file = tv.item(_id, "text")
            )

            if file_name:
                tv.item(_id, text = file_name)

                # This operation do not saves the patch.
                # So, file content likely does not correspond to renamed patch.
                # Mark the patch as changed to warn user about it.
                # TODO: should we waste time to check if file exists/equal?
                tv.item(_id, values = ["*"])

            break # one or none

    def _on_add_patch_above(self):
        self.notify_popup_command()

        tv = self._tv_patches

        for _id in tv.selection():
            self._add_empty_patch_set_at(self._tv_patches.index(_id), _id)
            break # one or none

    def _on_add_patch_below(self):
        self.notify_popup_command()

        tv = self._tv_patches

        for _id in tv.selection():
            self._add_empty_patch_set_at(self._tv_patches.index(_id) + 1, _id)
            break # one or none

    def _add_empty_patch_set_at(self, idx, near_iid):
        tv = self._tv_patches

        tv.insert("", idx,
            text = gen_similar_file_name(tv.item(near_iid, "text"),
                existing = set(self.patch_names)
            ),
            tags = [len(self._patch_sets)],
            values = ["*"] # it's not yet saved in file system
        )
        self._patch_sets.append(PatchSet(tuple()))

    def _on_load_patch_above(self):
        self.notify_popup_command()

        tv = self._tv_patches

        for _id in tv.selection():
            self._load_patch_set_at(self._tv_patches.index(_id))
            break # one or none

    def _on_load_patch_below(self):
        self.notify_popup_command()

        tv = self._tv_patches

        for _id in tv.selection():
            self._load_patch_set_at(self._tv_patches.index(_id) + 1)
            break # one or none

    def _on_load_patch(self):
        self.notify_popup_command()

        self._load_patch_set_at(len(self._tv_patches.get_children()))

    def _load_patch_set_at(self, idx):
        file_name = askopen(self,
            title = _("Select patch")
        )
        if not file_name:
            return

        try:
            patch_set = PatchSet.from_filename(file_name)
        except:
            ErrorDialog(
                summary = _("Errors during patch loading"),
                message = format_exc()
            ).wait()
            return

        tv = self._tv_patches

        tv.insert("", idx,
            text = file_name,
            tags = [len(self._patch_sets)]
        )
        self._patch_sets.append(patch_set)

    def iter_patch_names(self):
        # cache
        tv = self._tv_patches
        item = tv.item

        for c in tv.get_children():
            yield item(c, "text")

    @property
    def patch_names(self):
        return tuple(self.iter_patch_names())

    def _on_forget_patch(self):
        self.notify_popup_command()

        tv = self._tv_patches

        for _id in tv.selection():
            if not askyesno(self,
                title = _("Forget patch"),
                message = _(
"Patch\n\n%s\n\nwill be removed from the list. File is preserved. Continue?"
                ) % (
                    tv.item(_id, "text")
                )
            ):
                return

            self._patch_sets[self.get_patch_set_index(_id)] = None
            tv.delete(_id)

            break # one or none

    def get_patch_set_index(self, _id):
        return int(self._tv_patches.item(_id, "tags")[0])

    def _on_commit_info_applied(self, __):
        tv = self._tv_patches
        for _id in tv.selection():
            idx = self.get_patch_set_index(_id)
            patch_set = self._patch_sets[idx]

            try:
                file0 = patch_set[0]
            except IndexError:
                break

            ci = self._cef.commit_info

            if ci.last_parsed_line is None:
                file0.patch_info[:0] = ci.as_lines
            else:
                ci_lines = ci.as_lines
                file0.patch_info[:ci.last_parsed_line + 1] = ci_lines
                ci.last_parsed_line = len(ci_lines) - 1

            tv.item(_id, values = ["*"])
            break # one or none


class PatchEditor(
    GUITk,
    object # for `property` (Py2)
):

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self.title(_("Patch Editor"))

        hotkeys = self.hk
        hotkeys(
            self._save,
            key_code = 39,
            description = _("Save current patch."),
            symbol = "S"
        )
        hotkeys(
            self._reload,
            key_code = 27,
            description = _("Reload current patch."),
            symbol = "R"
        )

        self._psef = psef = PatchSeriesEditorFrame(self,
            sizegrip = True
        )
        psef.pack(fill = BOTH, expand = True)

    def _save(self):
        self._psef.save_current()

    def _reload(self):
        self._psef.reload_current(confirm = True)

    @property
    def patch_file_names(self):
        return self._psef.patch_file_names

    @patch_file_names.setter
    def patch_file_names(self, patch_file_names):
        self._psef.patch_file_names = patch_file_names


def main():
    ap = ArgumentParser(
        description = "Patch Editor"
    )
    ap.add_argument("patch",
        nargs = "*"
    )

    args = ap.parse_args()

    root = PatchEditor()
    root.patch_file_names = args.patch

    root.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
