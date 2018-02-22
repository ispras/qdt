from six.moves.tkinter_ttk import Treeview

from six.moves.tkinter_font import Font

class TreeviewWidthHelper(Treeview):
    def __init__(self, auto_columns = [], zero_column_extra_width = 40):
        self.auto_columns = list(auto_columns)
        self.zero_column_extra_width = zero_column_extra_width

    def get_max_width(self, iid, col, font, hidden):
        if col == 0:
            cell_val = self.item(iid, "text")
        else:
            row_vals = self.item(iid, "values")
            try:
                cell_val = row_vals[col - 1]
            except IndexError:
                cell_val = ""

        max_width = font.measure(cell_val)

        """ "open" attribute of "" (root) is 0 while it is always opened...
        Hence, iterate root children anyway. """
        if hidden or (not iid) or self.item(iid, "open"):
            for child_iid in self.get_children(iid):
                child_max = self.get_max_width(child_iid, col, font, hidden)

                if child_max > max_width:
                    max_width = child_max

        return max_width

    def adjust_widths(self, hidden = False):
        f = Font()

        for col_idx, col in enumerate(("#0",) + self.cget("columns")):
            if not col in self.auto_columns:
                continue

            col_max_len = f.measure(self.heading(col)["text"])

            max_cell_width = self.get_max_width("", col_idx, f, hidden)

            if col == "#0":
                max_cell_width += self.zero_column_extra_width

            cur_width = self.column(col, "width")
            max_width = max(col_max_len, max_cell_width)

            if cur_width < max_width or not self.column(col, "stretch"):
                self.column(col, width = max_width)
