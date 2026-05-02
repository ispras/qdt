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
from traceback import (
    print_exc,
)


def case_insens(v):
    return v.lower()

def case_insens_item(v):
    return case_insens(v[0])


class ICViewer(GUITk, object):

    def __init__(self, *a, **kw):
        GUITk.__init__(self, *a, **kw)

        self._title_base = _("Instruction Counters Viewer")
        self._json_file_names = []

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
        self._update = 1

    def account_json(self, *json_file_names):
        self._json_file_names.extend(json_file_names)
        self._update = 1

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

        instructions = defaultdict(lambda : defaultdict(int))
        encodings = set()

        consumed_jfnames = []

        for jfname in self._json_file_names:
            try:
                with open(jfname, "r") as f:
                    ic_json = f.read()
                ic = loads(ic_json)
                if not isinstance(ic, list):
                    raise NotImplementedError(
                        "IC_FORMAT_LISTS is only implemented"
                    )

                for enc_name, i_name, cnt in ic:
                    encodings.add(enc_name)
                    instructions[i_name][enc_name] += cnt
                    instructions[i_name][".total"] += cnt
            except:
                print_exc()
            else:
                consumed_jfnames.append(jfname)

        if not consumed_jfnames:
            return

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
          + repr(consumed_jfnames[0])
          + (" + %u" % (len(consumed_jfnames) - 1)
                if len(consumed_jfnames) > 1
                else ""
            )
        )


def main():
    ap = ArgumentParser()
    arg = ap.add_argument

    arg("ic_json_file",
        nargs = "*",
    )

    args = ap.parse_args()

    tk = ICViewer()
    tk.account_json(*args.ic_json_file)
    tk.mainloop()


if __name__ == "__main__":
    exit(main() or 0)
