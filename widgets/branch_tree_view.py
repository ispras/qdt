__all__ = [
    "BranchTreeview"
]

from .tv_width_helper import TreeviewWidthHelper

from .var_widgets import VarTreeview

from common import mlget as _

class BranchTreeview(VarTreeview, TreeviewWidthHelper):
    def __init__(self, gui_project_history_tracker, *args, **kw):
        kw["columns"] = [
            "description"
        ]

        VarTreeview.__init__(self, *args, **kw)

        TreeviewWidthHelper.__init__(self, ["#0"] + kw["columns"])

        self.guipht = gui_project_history_tracker

        self.sequence_ml = ml = _("Sequence")
        self.heading("#0", text = ml)
        self.__sequence_ml = ml.trace_variable("w",
            self.__on_heading_changed__
        )
        # width = 0 - columns will be expanded after __invalidate__
        self.column("#0", stretch = False, width = 0)

        self.description_ml = ml = _("Operation description")
        self.heading("description", text = ml)
        self.__description_ml = ml.trace_variable("w",
            self.__on_heading_changed__
        )
        self.column("description", stretch = False, width = 0)

        self.guipht.watch_changed(self.__on_operation__)

        self.bind("<Destroy>", self.__on_destroy__, "+")

        self.tag_configure("undone", foreground = "grey")

        self.bind("<<TreeviewOpen>>", self.__on_open_or_close__, "+")
        self.bind("<<TreeviewClose>>", self.__on_open_or_close__, "+")

        self.__invalidate__()

    def __on_open_or_close__(self, *args):
        """ The rows are not already opened or closed. So, give them time to
        do it. Then recompute widths. """
        self.__after_open_or_close = self.after_idle(
            self.__after_open_or_close__
        )

    def __after_open_or_close__(self):
        del self.__after_open_or_close
        self.adjust_widths()

    def __on_heading_changed__(self, *args):
        self.__invalidate__()

    def __on_destroy__(self, *args):
        self.sequence_ml.trace_vdelete("w", self.__sequence_ml)
        self.description_ml.trace_vdelete("w", self.__description_ml)
        self.guipht.unwatch_changed(self.__on_operation__)

        try:
            self.after_cancel(self.__refresh_after)
        except AttributeError:
            pass
        else:
            del self.__refresh_after

        try:
            self.after_cancel(self.__after_open_or_close)
        except AttributeError:
            pass
        else:
            del self.__after_open_or_close

    def __on_operation__(self, op):
        self.__invalidate__()

    def __invalidate__(self):
        try:
            self.after_cancel(self.__refresh_after)
        except AttributeError:
            pass

        # delay refreshing
        self.__refresh_after = self.after(10, self.__refresh_after__)

    def gen_seq_iid(self, sequence):
        return "seq.%d" % sequence

    def __refresh_after__(self):
        del self.__refresh_after

        existing_seq_iids = self.get_children()
        existing_seq_iids_iter = iter(existing_seq_iids)

        ops = self.guipht.get_branch()
        ops_iter = iter(ops)

        seq_counter = 0

        #print "Skip existing rows..."
        last_seq = None
        for op in ops_iter:
            op_seq = op.seq

            if op_seq != last_seq:
                last_seq = op_seq

                seq_counter += 1

                seq_iid = self.gen_seq_iid(op_seq)

                try:
                    ex_seq_iid = next(existing_seq_iids_iter)
                except StopIteration:
                    existing_seq_iids_iter = None
                    break

                if ex_seq_iid == seq_iid:
                    self.item(ex_seq_iid, tags = ())
                    for row_iid in self.get_children(ex_seq_iid):
                        self.item(row_iid, tags = ())
                else:
                    #print "Operations in the branch were changed, rebuild \
                    #them."

                    lost_iids = [ex_seq_iid] + list(existing_seq_iids_iter)
                    self.delete(*lost_iids)

                    existing_seq_iids_iter = None
                    break
        else:
            # print "No new sequences."

            for ex_seq_iid in existing_seq_iids_iter:
                self.item(ex_seq_iid, tags = ("undone"))
                for row_iid in self.get_children(ex_seq_iid):
                    self.item(row_iid, tags = ("undone"))

            return

        # print "Append new rows..."

        last_seq = None
        for op in [op] + list(ops_iter):
            op_seq = op.seq

            # add new rows
            if op_seq != last_seq:
                last_seq = op_seq

                seq_iid = self.gen_seq_iid(op_seq)

                if op_seq in self.guipht.sequence_strings:
                    desc = self.guipht.sequence_strings[op_seq]
                else:
                    desc = _("Sequence without description.")

                self.insert("", seq_counter,
                    iid = seq_iid,
                    text = str(op_seq),
                    values = [ desc ]
                )

                row_counter = 0
                seq_counter += 1

            if op in self.guipht.operation_strings:
                desc = self.guipht.operation_strings[op]
            else:
                desc = _("Is not done yet.")

            self.insert(seq_iid, row_counter, values = [desc])
            row_counter += 1

        self.adjust_widths()
