from common import (
    mlget as _,
)
from widgets import (
    add_scrollbars_native,
    ErrorDialog,
    GUIFrame,
    GUITk,
    tk_delayed,
    VarTreeview,
)


from argparse import (
    ArgumentParser,
)
from glob import (
    iglob,
    escape,
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

    def __missing__(self, i_cls_name):
        ret = InstructionClassStats()
        self[i_cls_name] = ret
        return ret


class InstructionClassStats(dict):

    def __missing__(self, i_name):
        ret = InstructionStats()
        self[i_name] = ret
        return ret


class InstructionStats(dict):

    def __missing__(self, enc_name):
        ret = 0
        self[enc_name] = ret
        return ret



def read_json_files(*json_file_names):
    instructions = InstructionCounters()
    encodings = set()

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
                encodings.add(enc_name)
                i_cls = i_name_match(i_name).group("cls")
                instructions[i_cls][i_name][enc_name] += cnt
                instructions[i_cls][i_name][".total"] += cnt
                instructions[i_cls][".cls"][enc_name] += cnt
                instructions[i_cls][".cls"][".total"] += cnt
        except:
            errors.append(format_exc())
        else:
            consumed_jfnames.append(jfname)

    return instructions, encodings, consumed_jfnames, errors


re_i_name = compile(r"(?P<name>(?P<cls>.*?)_(?P<n>\d+))")
i_name_match = re_i_name.match

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

        self._tv = tv = VarTreeview(f)
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

        m_instructions, __, __, m_errors = read_json_files(
            *self._masks_file_names
        )

        instructions, encodings, consumed_jfnames, errors = read_json_files(
            *self._json_file_names
        )

        errors += m_errors

        if errors:
            self._errors[:1] = reversed(errors)
            self._show_errors = 1

        if not consumed_jfnames:
            return

        # masking
        for m_i_cls, m_cls_stats in m_instructions.items():
            for m_i_name, m_enc_stats in m_cls_stats.items():
                if m_i_name.startswith("."):
                    continue
                for m_enc_name, m_cnt in m_enc_stats.items():
                    if m_enc_name.startswith("."):
                        continue
                    if not m_cnt:
                        continue
                    cls_stats = instructions[m_i_cls]
                    cnt = cls_stats[m_i_name][m_enc_name]
                    if not cnt:
                        continue
                    cls_stats[m_i_name][m_enc_name] = 0
                    cls_stats[m_i_name][".total"] -= cnt
                    cls_stats[".cls"][m_enc_name] -= cnt
                    cls_stats[".cls"][".total"] -= cnt

        encodings = list(sorted(encodings, key = case_insens))
        instructions = list(sorted(instructions.items(),
            key = case_insens_item
        ))

        tv.configure(
            columns = [".total"] + encodings,
        )
        tv.heading(".total", text = _("Total"))
        for enc_name in encodings:
            tv.heading(enc_name, text = enc_name)

        zeros = set()
        zeros_cls = set()
        partial_cls = set()
        total_i = 0

        for i_cls, cls_stats in instructions:
            cls_stats_cls = cls_stats[".cls"]

            cls_iid = tv.insert("", END,
                text = i_cls,
                values = list(
                    cls_stats_cls[enc_name] for enc_name in tv.cget("columns")
                ),
                open = True,
            )

            cls_have_zero = False

            for i_name, enc_stats in list(sorted(
                cls_stats.items(),
                key = case_insens_item
            )):
                if i_name.startswith('.'):
                    continue
                total_i += 1
                tags = []
                total = enc_stats[".total"]
                if not total:
                    cls_have_zero = True
                    tags.append("all_zero")
                    zeros.add(i_name)
                tv.insert(cls_iid, END,
                    text = i_name,
                    values = list(
                        enc_stats[enc_name] for enc_name in tv.cget("columns")
                    ),
                    tags = tags,
                )

            cls_tags = []
            if not cls_stats_cls[".total"]:
                cls_tags.append("all_zero")
                zeros_cls.add(i_cls)
            elif cls_have_zero:
                cls_tags.append("have_zero")
                partial_cls.add(i_cls)

            if cls_tags:
                tv.item(cls_iid, tags = cls_tags)

        total_cls = len(instructions)
        covered_cls = total_cls - len(zeros_cls)
        full_cls = covered_cls - len(partial_cls)
        covered_i = total_i - len(zeros)

        self.title(" ".join(
            [
                self._title_base.get(),
                "%u/%u" % (covered_i, total_i),
                "%u/%u/%u" % (
                    full_cls,
                    covered_cls,
                    total_cls
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
        nargs = "*",
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
