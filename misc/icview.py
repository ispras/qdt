from common import (
    mlget as _,
)
from widgets import (
    add_scrollbars_native,
    GUIFrame,
    GUITk,
    tk_delayed,
    VarTreeview,
)


from argparse import (
    ArgumentParser,
)
from collections import (
    defaultdict,
)
from json import (
    loads,
)
from six.moves.tkinter import (
    BOTH,
    END,
)


def case_insens(v):
    return v.lower()

def case_insens_item(v):
    return case_insens(v[0])


class ICViewer(GUITk, object):

    def __init__(self, *a, **kw):
        ic_json_file = kw.pop("ic_json_file", None)
        GUITk.__init__(self, *a, **kw)

        self._title_base = _("Instruction Counters Viewer")

        # widgets
        f = GUIFrame(self)
        f.pack(fill = BOTH, expand = True)

        f.rowconfigure(0, weight = 1)
        f.columnconfigure(0, weight = 1)

        self._tv = tv = VarTreeview(f)
        tv.grid(row = 0, column = 0, sticky = "NESW")
        add_scrollbars_native(f, tv, sizegrip = True)

        tv.heading("#0", text = _("Instruction"))

        tv.tag_configure("zero", background = "#FFFFAA")

        # startup
        if ic_json_file is not None:
            self.ic_json_file = ic_json_file
        self._update = 1

    _ic_json_file = None

    @property
    def ic_json_file(self):
        return self._ic_json_file

    @ic_json_file.setter
    def ic_json_file(self, ic_json_file):
        if self._ic_json_file == ic_json_file:
            return
        if ic_json_file is None:
            del self._ic_json_file
        else:
            self._ic_json_file = ic_json_file
        self._update = 1

    @tk_delayed
    def _update(self):
        ic_json_file = self._ic_json_file
        if ic_json_file is None:
            self._cleanup()
        else:
            self._fill()

    def _cleanup(self):
        tv = self._tv
        c = tv.get_children()
        if c:
            tv.delete(*c)
        tv.configure(columns = [])
        self.title(self._title_base.get())

    def _fill(self):
        ic_json_file = self._ic_json_file
        tv = self._tv

        with open(ic_json_file, "r") as f:
            ic_json = f.read()

        ic = loads(ic_json)
        if not isinstance(ic, list):
            raise NotImplementedError("IC_FORMAT_LISTS is only implemented")

        instructions = defaultdict(lambda : defaultdict(int))
        encodings = set()

        for enc_name, i_name, cnt in ic:
            encodings.add(enc_name)
            instructions[i_name][enc_name] += cnt
            instructions[i_name][".total"] += cnt

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

        for i, stats in instructions:
            tags = []
            total = stats[".total"]
            if not total:
                tags.append("zero")
                zeros.add(i)
            tv.insert("", END,
                text = i,
                values = list(
                    stats[enc_name] for enc_name in tv.cget("columns")
                ),
                tags = tags,
            )

        total = len(instructions)
        covered = total - len(zeros)

        self.title(
            self._title_base.get()
          + " %u/%u " % (covered, total)
          + " " + repr(ic_json_file)
        )


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("ic_json_file",
        nargs = "?",
        default = None,
    )

    args = ap.parse_args()

    tk = ICViewer()
    if args.ic_json_file is not None:
        tk.ic_json_file = args.ic_json_file
    tk.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
