from common import (
    mlget as _,
    iter_file_unique_subpaths,
)
from widgets import (
    add_scrollbars_native,
    ErrorDialog,
    GUIFrame,
    GUITk,
    tk_delayed,
    TreeviewWidthHelper,
    VarTreeview,
)


from argparse import (
    ArgumentParser,
)
from collections import (
    defaultdict,
)
from glob import (
    iglob,
)
from json import (
    loads,
)
from re import (
    compile,
)
from six.moves.tkinter import (
    BOTH,
    END,
)
from traceback import (
    format_exc,
)


def case_insens(v):
    return v.lower()

def case_insens_item(v):
    return case_insens(v[0])


class InstructionCounters(dict):

    mask = set()

    def __missing__(self, i_cls_name):
        ret = InstructionClassStats()
        self[i_cls_name] = ret
        return ret

    def account(self, enc_name, i_name, cnt, file_name):
        if (enc_name, i_name) in self.mask:
            return
        i_cls_name = i_name_match(i_name).group("cls")
        self[i_cls_name].account(enc_name, i_name, cnt, file_name)

    def gen_mask(self):
        mask = set()
        add = mask.add
        for __, i_cls_stats in self.items():
            for i_name, i_stats in i_cls_stats.items():
                if i_name.startswith("."):
                    continue
                for enc_name, cnt in i_stats.items():
                    if enc_name.startswith("."):
                        continue
                    if cnt:
                        add((enc_name, i_name))
        return mask

    def read_json_files(self, *json_file_names):
        account = self.account

        f2tag = dict(iter_file_unique_subpaths(json_file_names))

        consumed_jfnames = []
        errors = []

        for jfname in json_file_names:
            try:
                with open(jfname, "r") as f:
                    ic_json = f.read()
                ic = loads(ic_json)
                if not isinstance(ic, list):
                    raise NotImplementedError(
                        "%r: IC_FORMAT_LISTS is only implemented" % jfname
                    )

                for enc_name, i_name, cnt in ic:
                    account(enc_name, i_name, cnt, f2tag[jfname])
            except:
                errors.append(format_exc())
            else:
                consumed_jfnames.append(jfname)

        return consumed_jfnames, errors

    def analyze(self):
        total_cls = len(self)
        covered_cls = total_cls
        full_cls = 0
        covered_i = 0
        total_i = 0
        self.encodings = encodings = set()

        for __, i_cls_stats in self.items():
            i_cls_stats.analyze()
            if i_cls_stats.all_zero:
                covered_cls -= 1
            elif not i_cls_stats.have_zero:
                full_cls += 1
            covered_i += i_cls_stats.covered_i
            total_i += i_cls_stats.total_i
            encodings.update(i_cls_stats.encodings)

        self.total_cls = total_cls
        self.covered_cls = covered_cls
        self.full_cls = full_cls
        self.covered_i = covered_i
        self.total_i = total_i

    def fill_treeview(self, tv, parent_iid = ""):
        for i_cls, cls_stats in sorted(self.items(),
            key = case_insens_item,
        ):
            cls_stats_cls = cls_stats[".cls"]

            cls_tags = []
            if cls_stats.all_zero:
                cls_tags.append("all_zero")
            elif cls_stats.have_zero:
                cls_tags.append("have_zero")

            cls_iid = tv.insert(parent_iid, END,
                text = i_cls,
                values = list(
                    cls_stats_cls[enc_name] for enc_name in tv.cget("columns")
                ),
                open = True,
                tags = cls_tags,
            )

            cls_stats.fill_treeview(tv, parent_iid = cls_iid)


class InstructionClassStats(dict):

    def __missing__(self, i_name):
        ret = InstructionStats()
        self[i_name] = ret
        return ret

    def account(self, enc_name, i_name, cnt, file_name):
        self[i_name].account(enc_name, cnt, file_name)
        self[".cls"].account(enc_name, cnt, file_name)
        if cnt:
            self.all_zero = False

    def analyze(self):
        zero_i = 0
        covered_i = 0
        self.encodings = encodings = set()
        for i_name, i_stats in self.items():
            i_stats.analyze()
            if i_name.startswith('.'):
                continue
            if i_stats.all_zero:
                zero_i += 1
            else:
                covered_i += 1
            encodings.update(i_stats.encodings)
        self.zero_i = zero_i
        self.covered_i = covered_i
        self.total_i = covered_i + zero_i
        self.have_zero = bool(zero_i)
        self.all_zero = covered_i == 0

    def fill_treeview(self, tv, parent_iid = ""):
        for i_name, i_stats in sorted(
            self.items(),
            key = case_insens_item
        ):
            if i_name.startswith('.'):
                continue
            tags = []
            if i_stats.all_zero:
                tags.append("all_zero")
            iid = tv.insert(parent_iid, END,
                text = i_name + " in %u file(s)" % i_stats.total_files,
                values = list(
                    i_stats[enc_name] for enc_name in tv.cget("columns")
                ),
                tags = tags,
                open = (i_stats.total_files <= 5),
            )
            i_stats.fill_treeview(tv, iid)


class undefined_int(int):

    def __str__(self):
        return "-"


class InstructionStats(dict):

    def __init__(self):
        self.files = defaultdict(FileStats)

    def __missing__(self, enc_name):
        ret = undefined_int(0)
        self[enc_name] = ret
        return ret

    def account(self, enc_name, cnt, file_name):
        self[enc_name] += cnt
        self[".total"] += cnt
        self.files[file_name].account(enc_name, cnt)

    def analyze(self):
        self.all_zero = not self[".total"]
        self.encodings = set(n for n in self if not n.startswith('.'))
        total_files = 0
        for f_stats in self.files.values():
            f_stats.analyze()
            if f_stats[".total"]:
                total_files += 1
        self.total_files = total_files

    def fill_treeview(self, tv, parent_iid = ""):
        for file_name, f_stats in sorted(self.files.items()):
            if not f_stats[".total"]:
                continue
            iid = tv.insert(parent_iid, END,
                text = file_name,
                values = list(
                    f_stats[enc_name] for enc_name in tv.cget("columns")
                ),
            )
            f_stats.fill_treeview(tv, iid)



class FileStats(dict):

    def __missing__(self, enc_name):
        ret = undefined_int(0)
        self[enc_name] = ret
        return ret

    def account(self, enc_name, cnt):
        self[enc_name] += cnt
        self[".total"] += cnt

    def fill_treeview(self, tv, parent_iid = ""):
        pass

    def analyze(self):
        pass


re_i_name = compile(r"(?P<name>(?P<cls>.*?)_(?P<n>\d+))")
i_name_match = re_i_name.match


class ICTreeview(VarTreeview, TreeviewWidthHelper):

    def __init__(self, *a, **kw):
        VarTreeview.__init__(self, *a, **kw)
        TreeviewWidthHelper.__init__(self, ["#0"],
            widths_cache_size = None,
        )

        self.bind("<<TreeviewOpen>>", self.__adjust_widths_handler__, "+")
        self.bind("<<TreeviewClose>>", self.__adjust_widths_handler__, "+")
        self.bind("<Configure>", self.__adjust_widths_handler__, "+")
        self.bind("<Destroy>", self.__on_destroy__, "+")

    def __adjust_widths_handler__(self, *__):
        self.adjust_widths_delayed = 0

    @tk_delayed
    def adjust_widths_delayed(self):
        self.adjust_widths()

    def __on_destroy__(self, *__):
        del self.adjust_widths_delayed


class ICViewer(GUITk, object):

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self._title_base = _("Instruction Counters Viewer")
        self._json_file_names = []
        self._masks_file_names = []
        self._errors = []

        # widgets
        f = GUIFrame(self)
        f.pack(fill = BOTH, expand = True)

        f.rowconfigure(0, weight = 1)
        f.columnconfigure(0, weight = 1)

        self._tv = tv = ICTreeview(f)
        tv.grid(row = 0, column = 0, sticky = "NESW")
        add_scrollbars_native(f, tv, sizegrip = True)

        tv.heading("#0", text = _("Instruction"))

        tv.tag_configure("have_zero", background = "#FFFFAA")
        tv.tag_configure("all_zero", background = "#FFDDAA")

        # startup
        self._update = 1

    def account_json(self, *json_file_names):
        self._json_file_names.extend(json_file_names)
        self._update = 1

    def account_masks(self, *json_file_names):
        self._masks_file_names.extend(json_file_names)
        self._update = 1

    @tk_delayed
    def _show_errors(self):
        ErrorDialog(
            summary = _("Errors during JSON files processing"),
            message = "\n\n\n".join(self._errors)
        ).wait()

    @tk_delayed
    def _update(self):
        self._cleanup()
        self._fill()

    def _cleanup(self):
        tv = self._tv
        c = tv.get_children()
        if c:
            tv.delete(*c)
        tv.configure(columns = [])
        self.title(self._title_base.get())

    def _fill(self):
        tv = self._tv

        jfns = self._json_file_names

        jfn_set = set(jfns)
        masks = []
        append = masks.append
        for f in self._masks_file_names:
            if f in jfn_set:
                print("%r: mask ignored: can't mask itself" % (f,))
                continue
            append(f)

        m_instructions = InstructionCounters()
        __, m_errors = m_instructions.read_json_files(*masks)

        instructions = InstructionCounters()
        instructions.mask = m_instructions.gen_mask()
        consumed_jfnames, errors = instructions.read_json_files(*jfns)

        errors += m_errors

        if errors:
            self._errors[:1] = reversed(errors)
            self._show_errors = 1

        if not consumed_jfnames:
            return

        instructions.analyze()

        encodings = list(sorted(instructions.encodings, key = case_insens))

        tv.configure(
            columns = [".total"] + encodings,
        )
        tv.heading(".total", text = _("Total"))
        for enc_name in encodings:
            tv.heading(enc_name, text = enc_name)

        instructions.fill_treeview(tv)

        self.title(" ".join(
            [
                self._title_base.get(),
                "%u/%u" % (instructions.covered_i, instructions.total_i),
                "%u/%u/%u" % (
                    instructions.full_cls,
                    instructions.covered_cls,
                    instructions.total_cls
                ),
                repr(consumed_jfnames[0]),
            ]
          + (
                ["+ %u" % (len(consumed_jfnames) - 1)]
                    if len(consumed_jfnames) > 1 else
                []
            )
        ))


def iter_glob(*files):
    for f in files:
        yield from iglob(f)


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("ic_json_file",
        nargs = "*",
    )
    arg("-m", "--mask",
        metavar = "ic_json_file",
        help = """
Non-zero entries in mask file(s) zeroises corresponding entries in final table.
This helps highlight test (set) unique instructions.
"""     ,
        action = "append",
    )

    args = ap.parse_args()

    tk = ICViewer()
    tk.account_json(*iter_glob(*args.ic_json_file))
    masks = args.mask
    if masks:
        tk.account_masks(*iter_glob(*masks))
    tk.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
