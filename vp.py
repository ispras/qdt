from common import (
    execfile,
    PyGenerator,
    mlget as _
)
from widgets import (
    VarButton,
    HKEntry,
    VarToplevel,
    CanvasDnD,
    VarTk
)
from inspect import (
    getmro,
    isclass
)
from math import (
    pi,
    sin,
    cos,
    atan2
)
from bisect import (
    bisect_left
)
from six.moves.tkinter import (
    END,
    StringVar
)
from os.path import (
    isfile
)
from traceback import (
    print_exc,
    format_exc
)
from six import (
    integer_types
)
from os import (
    rename,
    remove
)
from collections import (
    defaultdict
)


class Const(object):
    ico = u"Const"

    def __init__(self, str_value = None):
        self.str_value = str_value

    def __dfs_children__(self):
        return tuple()

    def __gen_code__(self, g):
        g.gen_code(self)

    def __var_base__(self):
        return "c"


class Op(object):
    ico = None
    # no limitations for operands amount
    # either integer or tuple of 2 integers (min & max)
    op_amount = None
    # no information about return values amount
    ret_amount = None

    def __init__(self, *operands):
        self.operands = _ops = [None] * self.op_amount
        for i, o in enumerate(operands):
            _ops[i] = o

    def __getitem__(self, idx):
        return self.operands[idx]

    def __gen_code__(self, g):
        g.reset_gen_common(type(self).__name__)
        g.pprint(tuple(self.operands))

    def __dfs_children__(self):
        return [op for op in self.operands if op is not None]

    def __var_base__(self):
        return type(self).__name__.lower()


class OpDef(object):
    "Value defined by an operator"
    def __init__(self, op, ret_idx):
        self.op, self.ret_idx = op, ret_idx

    def __hash__(self):
        return hash((self.op, self.ret_idx))

    def __eq__(self, opdef):
        return (self.op is opdef.op) and (self.ret_idx == opdef.ret_idx)

    def __var_base__(self):
        return type(self.op).__name__.lower() + ("_%u" % self.ret_idx)

    def __dfs_children__(self):
        return [self.op]

    def __gen_code__(self, g):
        g.gen_code(self)


class Bin(Op):
    __py_op__ = None
    op_amount = 2 # exactly 2 operands
    ret_amount = 1 # returns 1 value

    def __py__(self, w):
        self[0].__py__(w)
        w(self.__py_op__)
        self[1].__py__(w)


class Add(Bin):
    ico = u"+"
    __py_op__ = "+"

    def __eval__(self, a, b):
        return a + b


class Sub(Bin):
    ico = u"\u2212"
    __py_op__ = "-"

    def __eval__(self, a, b):
        return a - b


class Mul(Bin):
    ico = u"\u00d7"
    __py_op__ = "*"

    def __eval__(self, a, b):
        return a * b


class Div(Bin):
    ico = u"/"
    __py_op__ = "/"

    def __eval__(self, a, b):
        return a / b


class IntDiv(Bin):
    ico = u"//"
    __py_op__ = "//"

    def __eval__(self, a, b):
        return a // b


class Mod(Bin):
    ico = u"mod"
    __py_op__ = "%"

    def __eval__(self, a, b):
        return a % b


class DnDGroup(object):
    def __init__(self, w, anchor_id, items):
        self.anchor_id = anchor_id
        self.items = list(items)
        w.bind("<<DnDDown>>", self.on_dnd_down, "+")

    def on_dnd_down(self, event):
        w = event.widget
        a_id = self.anchor_id
        if w.dnd_dragged != a_id:
            return
        self.prev = w.canvas.coords(a_id)[:2]
        self.__moved = w.bind("<<DnDMoved>>", self.on_dnd_moved, "+")
        self.__up = w.bind("<<DnDUp>>", self.on_dnd_up, "+")

    def add_item(self, iid, first_coord = None, end = None):
        if first_coord is None:
            self.items.append(iid)
        else:
            self.items.append((iid, first_coord, end))

    def del_item(self, iid):
        self.items = [i for i in self.items if (
            (i != iid) if isinstance(i, integer_types) else (i[0] != iid)
        )]

    def on_dnd_moved(self, event):
        w = event.widget
        a_id = self.anchor_id
        px, py = self.prev

        x, y = w.canvas.coords(a_id)[:2]
        dx, dy = x - px, y - py
        self.prev = x, y

        coords = w.canvas.coords
        for i in self.items:
            if isinstance(i, integer_types):
                xy = coords(i)
                if len(xy) == 2:
                    x0, y0 = xy
                    coords(i, x0 + dx, y0 + dy)
                else:
                    x0, y0, x1, y1 = xy                    coords(i, x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            elif isinstance(i, tuple):
                iid, first_coord, end = i
                c = coords(iid)
                if end is None:
                    end = len(c)
                for idx in range(first_coord, end):
                    if idx & 1:
                        c[idx] += dy
                    else:
                        c[idx] += dx
                coords(iid, *c)
            else:
                raise ValueError(
                    "Unsupported type of item: " + type(i).__name__
                )

    def on_dnd_up(self, event):
        w = event.widget
        w.unbind("<<DnDMoved>>", self.__moved)
        w.unbind("<<DnDUp>>", self.__up)


class Wgt(object):
    def __init__(self, instance):
        self.inst = instance

def bbox_center(bbox):
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2

def slot(x, y):
    return x - 10, y - 10, x + 10, y + 10


class OpWgt(Wgt):

    def __init__(self, op):
        super(OpWgt, self).__init__(op)
        self.op_id = None

        # widget id to operand index
        self.in_slots = {}
        self.out_slots = {}

    def __g_init__(self, w, x, y):
        c = w.canvas
        op = self.inst

        in_slots = self.in_slots
        I = op.op_amount
        step = pi / I
        a = -pi + step / 2

        rad = 30

        for i in range(I):
            sx, sy = x + rad * cos(a), y + rad * sin(a)
            in_slots[c.create_oval(slot(sx, sy), fill = "white")] = i
            a += step

        out_slots = self.out_slots
        I = op.ret_amount
        step = pi / I
        a = pi - step / 2

        for i in range(I):
            sx, sy = x + rad * cos(a), y + rad * sin(a)
            out_slots[c.create_rectangle(slot(sx, sy), fill = "white")] = i
            a -= step

        op_id = c.create_text(x, y, text = op.ico, tag = "DnD")
        self.op_id = op_id
        # bounds = c.bbox(op_id)
        # width = bounds[2] - bounds[0]
        # height = bounds[3] - bounds[1]
        # c.coords(op_id, x - width / 2, y - height / 2)
        self.dnd_group = DnDGroup(w, op_id,
            tuple(self.in_slots) + tuple(self.out_slots)
        )

    def __g_update__(self, w):
        ops = self.inst.operands
        dc = w.data_colors
        iconfig = w.canvas.itemconfig

        for iid, idx in self.in_slots.items():
            datum_id = ops[idx]
            if datum_id in dc:
                color1, color2 = dc[datum_id]
            else:
                color1, color2 = "white", "black"
            iconfig(iid, fill = color1, outline = color2)

        for iid, idx in self.out_slots.items():
            datum_id = self.get_datum(iid)
            if datum_id in dc:
                color1, color2 = dc[datum_id]
            else:
                color1, color2 = "white", "black"
            iconfig(iid, fill = color1, outline = color2)

    def __g_coords__(self, w):
        return w.canvas.coords(self.op_id)

    def ids(self):
        return (self.op_id,) + tuple(self.in_slots) + tuple(self.out_slots)

    def out_ids(self):
        return self.out_slots.keys()

    def in_ids(self):
        return self.in_slots.keys()

    def get_datum(self, iid):
        return OpDef(self.inst, self.out_slots[iid])

    def set_datum(self, iid, datum_id):
        self.inst.operands[self.in_slots[iid]] = datum_id

    def get_used(self):
        return self.inst.__dfs_children__()

    def get_defined(self):
        inst = self.inst
        return [OpDef(inst, i) for i in range(inst.op_amount)]

    def slots(self):
        return enumerate(self.inst.operands)

    def get_slot_idx(self, iid):
        return self.in_slots[iid]

    def get_slot(self, iid):
        return self.inst.operands[self.in_slots[iid]]

CONST_PADDING = 5


class ConstWgt(Wgt):
    def __init__(self, const = None):
        super(ConstWgt, self).__init__(Const() if const is None else const)

    def __g_init__(self, w, x, y):
        c = w.canvas

        # actual frame and drag-box sizes will be assigned by `__g_update__`
        self.frame_id = c.create_rectangle(x, y, x, y, fill = "white")
        self.drag_id = c.create_rectangle(x, y, x, y,
            fill = "black",
            tag = "DnD"
        )
        self.text_id = c.create_text(x, y, text = "")

        self.dnd_group = DnDGroup(w, self.drag_id,
            [self.text_id, self.frame_id]
        )

    def __g_update__(self, w):
        c = w.canvas
        inst = self.inst

        text_id = self.text_id
        frame_id = self.frame_id
        drag_id = self.drag_id

        val = inst.str_value

        color = "black"
        if val is None:
            text = ""
        elif val == "":
            text = '""'
            color = "gray"
        else:
            text = val

        if inst in w.data_colors:
            color1, color2 = w.data_colors[inst]
        else:
            color1, color2 = "white", "black"

        c.itemconfig(frame_id, outline = color2)
        c.itemconfig(drag_id, fill = color1, outline = color2)
        c.itemconfig(text_id, text = text, fill = color)

        bounds = c.bbox(text_id)
        c.coords(frame_id,
            bounds[0] - CONST_PADDING, bounds[1] - CONST_PADDING,
            bounds[2] + CONST_PADDING, bounds[3] + CONST_PADDING
        )
        c.coords(drag_id,
            bounds[0] - 3 * CONST_PADDING, bounds[1] - 3 * CONST_PADDING,
            bounds[0] - CONST_PADDING, bounds[1] - CONST_PADDING
        )

    def __g_coords__(self, w):
        return w.canvas.coords(self.text_id)

    def ids(self):
        return [self.text_id, self.frame_id, self.drag_id]

    def out_ids(self):
        return [self.frame_id]

    def in_ids(self):
        return []

    def get_datum(self, iid):
        if iid != self.frame_id:
            raise ValueError(
                "Datum is represented by item %u rather that %u" % (
                    self.frame_id, iid
                )
            )
        return self.inst

    def set_datum(self, *a, **kw):
        raise TypeError("Constant does not have a datum to set.")

    def get_used(self):
        return []

    def get_defined(self):
        return [self.inst]

    def slots(self):
        return []


class VarDialog(VarToplevel):
    def __init__(self, *a, **kw):
        VarToplevel.__init__(self, *a, **kw)

        self.transient(self.master)
        self.grab_set()


class ConstEdit(VarDialog):
    def __init__(self, const_wgt, *a, **kw):
        VarDialog.__init__(self, *a, **kw)

        self.title(_("Edit constant"))

        self.cw = const_wgt

        self.grid()
        self.rowconfigure(0, weight = 1)
        self.rowconfigure(1, weight = 0)
        self.columnconfigure(0, weight = 1)
        self.columnconfigure(1, weight = 1)

        v = self.var = StringVar()
        e = self.entry = HKEntry(self, textvariable = v)
        e.grid(row = 0, column = 0, columnspan = 2, sticky = "NESW")

        e.focus_set()

        val = const_wgt.inst.str_value

        if val is None:
            v.set("")
        elif val == "":
            v.set('""')
        else:
            v.set(val)

        VarButton(self, text = _(u"Ok"), command = self.on_ok).grid(
            row = 1, column = 0, sticky = "W"
        )
        VarButton(self, text = _(u"Cancel"), command = self.on_cancel).grid(
            row = 1, column = 1, sticky = "E"
        )

        self.bind("<Return>", self.on_ok, "+")
        self.bind("<Escape>", self.on_cancel, "+")

        self.after(10, self.after_init)

    def after_init(self):
        e = self.entry

        e.selection_range(0, END)
        e.icursor(END)

    def on_cancel(self, __ = None):
        # __ is required to use this as a keyboard event key handler
        self.destroy()

    def on_ok(self, __ = None):
        cw = self.cw

        val = self.var.get()
        if val == "":
            cw.inst.str_value = None
        elif val == '""' or val == "''" or val == '""""""' or val == "''''''":
            cw.inst.str_value = ""
        else:
            cw.inst.str_value = val

        cw.__g_update__(self.master)
        self.destroy()


OPERATORS = [x for x in globals().values() if (
    isclass(x)
    and Op in getmro(x)
    and x.ico is not None
)]

# operator selection circle
OP_CIRCLE_R = 100
# operator selection highlighting
OP_HL_CIRCLE_R = 20
OP_HL_THRESHOLD_1 = 50.0 ** 2
OP_HL_THRESHOLD_2 = 150.0 ** 2

SHORTCUTS = tuple(OPERATORS + [
    Const
])

DATA_REMOVE_R = 50

class move_centred(object):
    def __init__(self, wgt, x, y, w = None, h = None):
        self.wgt, self.x, self.y, self.w, self.h = wgt, x, y, w, h
        wgt.after(10, self.move_centred)

    def move_centred(self):
        wgt = self.wgt

        w, h = self.w, self.h
        if w is None:
            w = wgt.winfo_width()
        if h is None:
            h = wgt.winfo_height()

        wgt.geometry("%ux%u+%u+%u" % (
            w, h, self.x - (w >> 1), self.y - (h >> 1)
        ))


def color_generator(seed = 0xff0000):
    _next = seed
    while True:
        yield _next >> 16, (_next >> 8) & 0xff, _next & 0xff
        _next = (_next + 202387) & 0x00FFFFFF

def color_string_generator(**kw):
    for r, g, b in color_generator(**kw):
        yield (
            "#%02x%02x%02x" % (r, g, b),
            "#%02x%02x%02x" % (
                max(r - 20, 0),
                max(g - 20, 0),
                max(b - 20, 0)
            )
        )


class DatumLine(object):
    def __init__(self, w, datum_id, dest_inst, dest_idx):
        cnv = w.canvas

        dst_wgt = w.inst2wgt[dest_inst]
        dst_iid = list(dst_wgt.in_ids())[dest_idx]

        dst_bbox = cnv.bbox(dst_iid)
        dx, dy = bbox_center(dst_bbox)

        src_wgt = w.did2wgt[datum_id]
        for src_idx, did in enumerate(src_wgt.get_defined()):
            if did == datum_id:
                break
        src_iid = list(src_wgt.out_ids())[src_idx]

        src_bbox = cnv.bbox(src_iid)
        sx, sy = bbox_center(src_bbox)

        color = w.data_colors[datum_id]
        line_id = cnv.create_line(sx, sy, dx, dy, fill = color)

        cnv.lower(line_id)

        src_wgt.dnd_group.add_item(line_id, first_coord = 0, end = 2)
        dst_wgt.dnd_group.add_item(line_id, first_coord = 2)


        self.dst_iid = dst_iid
        self.src_iid = src_iid
        self.line_id = line_id

    def __g_cleanup__(self, w):
        line_id = self.line_id

        w.id2wgt[self.src_iid].dnd_group.del_item(line_id)
        w.id2wgt[self.dst_iid].dnd_group.del_item(line_id)

        w.canvas.delete(line_id)

class CodeCanvas(CanvasDnD):
    def __init__(self, *a, **kw):
        CanvasDnD.__init__(self, *a, *kw)
        self.__b1_down = None

        # operator addition
        self.__ops_shown = False
        self.__ops_ids = []
        self.__op_circle = None
        self.__op_hl_idx = None

        self.id2wgt = {}
        self.in_ids = set()
        self.out_ids = set()

        self.canvas.bind("<Double-Button-1>", self.on_double_button_1, "+")

        # data dragging
        self.__data_drag = False
        self.__data_tmp_line = None

        # data removing (from slot)
        self.__data_removing = False
        self.__data_tmp_oval = None

        self.__color_gen_state = color_string_generator()
        self.data_colors = {}
        # datum id to widget of its source
        self.did2wgt = {}
        # data instance to widget
        self.inst2wgt = {}

        # (source data id, destination inst., dest. idx) -> line
        self.lines = {}

        # datum id -> list of users (inst, idx)
        self.users = defaultdict(list)

    def on_double_button_1(self, event):
        c = self.canvas

        ex, ey = event.x, event.y
        x, y = c.canvasx(ex), c.canvasy(ey)

        touched = c.find_overlapping(x - 1, y - 1, x + 1, y + 1)
        i2w = self.id2wgt

        for i in touched:
            if i not in i2w:
                continue

            wgt = i2w[i]

            if isinstance(wgt, ConstWgt):
                move_centred(ConstEdit(wgt, self),
                    c.winfo_rootx() + ex,
                    c.winfo_rooty() + ey,
                    w = 200
                )
                break

    # overrides
    def down(self, event):
        # Before DnD tagged widgets drawing check for data dragging
        cnv = self.canvas

        x, y = event.x, event.y
        self.__b1_down = (x, y)

        out_ids = self.out_ids
        in_ids = self.in_ids
        for _id in cnv.find_overlapping(x - 1, y - 1, x + 1, y + 1):
            if _id in out_ids:
                self.__data_start = _id
                self.__data_drag = True
                self.__data_tmp_line = cnv.create_line(x, y, x + 1, y + 1)
                return
            elif _id in in_ids:
                wgt = self.id2wgt[_id]
                if wgt.get_slot(_id) is None:
                    return
                self.__data_start = _id
                self.__data_removing = True

                bbox = cnv.bbox(_id)
                ox, oy = bbox_center(bbox)

                self.__data_tmp_oval = cnv.create_oval(
                    ox - DATA_REMOVE_R, oy - DATA_REMOVE_R,
                    ox + DATA_REMOVE_R, oy + DATA_REMOVE_R,
                    outline = "gray"
                )
                return

        CanvasDnD.down(self, event)

        if not self.dragging:
            self.show_ops(x, y)


    def up(self, event):
        if self.__data_drag:
            self.__data_drag = False
            self.canvas.delete(self.__data_tmp_line)
            self.__data_tmp_line = None

            x, y = event.x, event.y
            in_ids = self.in_ids

            for end_id in self.canvas.find_overlapping(
                x - 1, y - 1, x + 1, y + 1
            ):
                if end_id in in_ids:
                    break
            else:
                return

            i2w = self.id2wgt

            start_id = self.__data_start
            start = i2w[start_id]
            end = i2w[end_id]

            datum_id = start.get_datum(start_id)
            if datum_id not in self.data_colors:
                self.data_colors[datum_id] = next(self.__color_gen_state)

            if end.get_slot(end_id) is not None:
                self.remove_datum_from_slot(end_id)

            end.set_datum(end_id, datum_id)

            start.__g_update__(self)
            end.__g_update__(self)

            self.update_lines(end)
            return

        elif self.__data_removing:
            self.__data_removing = False
            cnv = self.canvas

            bbox = cnv.bbox(self.__data_tmp_oval)

            cnv.delete(self.__data_tmp_oval)

            ox, oy = bbox_center(bbox)
            x, y = event.x, event.y
            dx, dy = x - ox, y - oy

            if dx ** 2 + dy ** 2 >= DATA_REMOVE_R ** 2:
                self.remove_datum_from_slot(self.__data_start)
            return

        hl_idx = self.__op_hl_idx
        if hl_idx is not None:
            cls = SHORTCUTS[hl_idx]
            if cls is Const:
                wgt = ConstWgt()
            else:
                wgt = OpWgt(cls())

            self.add_widget(wgt, *self.__b1_down)

        self.hide_ops()

        self.__b1_down = None
        CanvasDnD.up(self, event)

    def remove_datum_from_slot(self, iid):
        wgt = self.id2wgt[iid]

        did, inst, idx = wgt.get_slot(iid), wgt.inst, wgt.get_slot_idx(iid)

        self.remove_line(did, inst, idx)

        users = self.users[did]
        users.remove((inst, idx))

        wgt.set_datum(iid, None)
        wgt.__g_update__(self)

        if not users:
            self.data_colors.pop(did)
            self.did2wgt[did].__g_update__(self)

    def remove_line(self, datum_id, inst, idx):
        line = self.lines.pop((datum_id, inst, idx))
        line.__g_cleanup__(self)

    def update_lines(self, wgt):
        lines = self.lines
        inst = wgt.inst
        users = self.users
        for idx, datum_id in wgt.slots():
            if datum_id is None:
                continue
            key = datum_id, inst, idx
            if key in lines:
                continue
            users[datum_id].append((inst, idx))
            line = DatumLine(self, *key)
            self.lines[key] = line

    def add_widget(self, wgt, x, y, assing_colors = True):
        wgt.__g_init__(self, x, y)

        self.inst2wgt[wgt.inst] = wgt

        i2w = self.id2wgt
        for i in wgt.ids():
            i2w[i] = wgt

        self.in_ids.update(wgt.in_ids())
        self.out_ids.update(wgt.out_ids())

        did2wgt = self.did2wgt
        for datum_id in wgt.get_defined():
            did2wgt[datum_id] = wgt

        if assing_colors:
            self.assing_colors(wgt)
        else:
            wgt.__g_update__(self)

    def assing_colors(self, wgt):
        did2wgt = self.did2wgt
        dc = self.data_colors
        for datum_id in wgt.get_used():
            if datum_id in dc:
                continue
            dc[datum_id] = next(self.__color_gen_state)
            did2wgt[datum_id].__g_update__(self)

        wgt.__g_update__(self)

        self.update_lines(wgt)

    def add_instance(self, inst, x, y, assing_colors = True):
        t = type(inst)
        for cls in getmro(t):
            if cls is Const:
                wgt = ConstWgt(inst)
                break
            elif cls is Op:
                wgt = OpWgt(inst)
                break
        else:
            raise ValueError("No widget for object %s of type %s" % (
                str(inst), t.__name__
            ))

        self.add_widget(wgt, x, y, assing_colors = assing_colors)
        return wgt

    def add_instances(self, instances):
        for wgt in [
            self.add_instance(*inst, assing_colors = False)
                for inst in instances
        ]:
            self.assing_colors(wgt)

    def iter_widgets(self):
        yielded = set()
        for w in self.id2wgt.values():
            if w in yielded:
                continue
            yield w
            yielded.add(w)

    def motion(self, event):
        if self.__data_drag:
            cnv = self.canvas

            x1, y1 = self.__b1_down
            x2, y2 = event.x, event.y
            line_id = self.__data_tmp_line

            cnv.coords(line_id, x1, y1, x2, y2)
            return

        CanvasDnD.motion(self, event)

        if self.dragging:
            return

        if self.__ops_shown:
            x, y = event.x, event.y
            dx, dy = x - self.__b1_down[0], y - self.__b1_down[1]

            r2 = dx ** 2 + dy ** 2
            if OP_HL_THRESHOLD_1 < r2 and r2 < OP_HL_THRESHOLD_2:
                a = atan2(dy, dx)

                idx = bisect_left(self.__op_segments, a)
                idx %= len(SHORTCUTS)
                self.__op_hl_idx = idx

                # print(SHORTCUTS[idx].__name__)

                op_a = self.__op_segments[idx] - self.__op_step / 2
                op_x, op_y = (
                    self.__b1_down[0] + OP_CIRCLE_R * cos(op_a),
                    self.__b1_down[1] + OP_CIRCLE_R * sin(op_a)
                )

                oval = (
                    op_x - OP_HL_CIRCLE_R, op_y - OP_HL_CIRCLE_R,
                    op_x + OP_HL_CIRCLE_R, op_y + OP_HL_CIRCLE_R
                )

                cnv = self.canvas

                circ = self.__op_circle
                if circ is None:
                    circ = cnv.create_oval(oval)
                    self.__op_circle = circ
                else:
                    cnv.coords(circ, oval)
            else:
                self.__hide_op_hl()

    def __hide_op_hl(self):
        "hides operator selection highlighting"
        circ = self.__op_circle
        if circ is not None:
            self.canvas.delete(circ)
            self.__op_circle = None
            self.__op_hl_idx = None

    def show_ops(self, x, y):
        if self.__ops_shown:
            return

        self.__ops_shown = True

        cnv = self.canvas
        ids = self.__ops_ids

        step = 2.0 * pi / len(SHORTCUTS)
        a = -pi

        # for user selection identification
        seg = a + step / 2
        op_segments = []
        for op in SHORTCUTS:
            ids.append(
                cnv.create_text(
                    (x + OP_CIRCLE_R * cos(a), y + OP_CIRCLE_R * sin(a)),
                    text = op.ico
                )
            )
            op_segments.append(seg)
            a += step
            seg += step

        self.__op_step = step
        self.__op_segments = op_segments

    def hide_ops(self):
        if self.__ops_shown:
            self.__ops_shown = False

            cnv = self.canvas
            for _id in self.__ops_ids:
                cnv.delete(_id)
            self.__ops_ids.clear()

            self.__hide_op_hl()

    def iter_positions(self):
        for wgt in self.iter_widgets():
            x, y = wgt.__g_coords__(self)
            yield wgt.inst, x, y


class SaveData(object):
    def __init__(self, *positions):
        self.positions = positions

    def from_canvas(self, cnv):
        self.positions = list(cnv.iter_positions())

    def to_canvas(self, cnv):
        cnv.add_instances(self.positions)

    def __dfs_children__(self):
        return [p[0] for p in self.positions]

    def __gen_code__(self, g):
        g.reset_gen_common(type(self).__name__)
        g.pprint(tuple(self.positions))

    def __var_base__(self):
        return "save"


if __name__ == "__main__":
    root = VarTk()
    root.grid()
    root.rowconfigure(0, weight = 1)
    root.columnconfigure(0, weight = 1)

    dnd_cnv = CodeCanvas(root)
    dnd_cnv.grid(row = 0, column = 0, sticky = "NESW")

    root.geometry("800x800+400+400")

    # last project loading
    if isfile("vproject.py"):
        loaded = {}
        try:
            execfile("vproject.py", globals(), loaded)
        except:
            print("Cannot load project file:\n" + format_exc())
        else:
            if "save" in loaded:
                loaded["save"].to_canvas(dnd_cnv)
            else:
                print("No save data found in project file")

    def do_save_and_destroy():
        save = SaveData()
        save.from_canvas(dnd_cnv)

        try:
            with open("vproject.py.tmp", "wb") as w:
                PyGenerator().serialize(w, save)
        except:
            print_exc()
            return
        else:
            if isfile("vproject.py"):
                remove("vproject.py")
            rename("vproject.py.tmp", "vproject.py")

        root.destroy()

    root.protocol("WM_DELETE_WINDOW", do_save_and_destroy)

    root.mainloop()
