__all__ = [
    "DnDGroup"
  , "bbox_center"
  , "ANCHOR_FIRST"
]

from six import (
    integer_types
)
from math import (
    sin,
    cos
)


def bbox_center(bbox):
    return (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2


def ANCHOR_FIRST(cnv, iid):
    return cnv.coords(iid)[:2]

class DnDGroup(object):
    """ Helps to drag, rotate and scale a group of `DnDCanvas` items (or some
    of theirs coordinates).
    """

    def __init__(self, w, anchor_id, items, anchor_point = ANCHOR_FIRST):
        self.anchor_id = anchor_id
        self.items = list(items)
        self.anchor_point = anchor_point
        w.bind("<<DnDDown>>", self.on_dnd_down, "+")

    def on_dnd_down(self, event):
        w = event.widget
        a_id = self.anchor_id
        if w.dnd_dragged != a_id:
            return
        self.prev = self.anchor_point(w, a_id)
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

        x, y = self.anchor_point(w, a_id)
        dx, dy = x - px, y - py
        self.prev = x, y

        # Unbind self dragging handlers because of dragging emulation for items
        w.unbind("<<DnDMoved>>", self.__moved)
        w.unbind("<<DnDUp>>", self.__up)

        coords = w.coords
        for i in self.items:
            if isinstance(i, integer_types):
                # Emulate dragging for the item
                w.dnd_dragged = i
                w.event_generate("<<DnDDown>>")

                xy = coords(i)
                if len(xy) == 2:
                    x0, y0 = xy
                    coords(i, x0 + dx, y0 + dy)
                else:
                    x0, y0, x1, y1 = xy
                    coords(i, x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            elif isinstance(i, tuple):
                iid, first_coord, end = i

                # Emulate dragging
                w.dnd_dragged = iid
                w.event_generate("<<DnDDown>>")

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

            # Emulate dragging
            w.event_generate("<<DnDMoved>>")
            w.event_generate("<<DnDUp>>")

        # End of dragging emulation
        w.dnd_dragged = a_id
        self.__moved = w.bind("<<DnDMoved>>", self.on_dnd_moved, "+")
        self.__up = w.bind("<<DnDUp>>", self.on_dnd_up, "+")

    def on_dnd_up(self, event):
        w = event.widget
        w.unbind("<<DnDMoved>>", self.__moved)
        w.unbind("<<DnDUp>>", self.__up)

    def rotate(self, w, a, cx, cy):
        coords = w.coords
        bbox = w.bbox
        cosa, sina = cos(a), sin(a)
        for i in self.items:
            if isinstance(i, integer_types):
                # only "center point" of item is rotated, item's points are
                # translated accordingly
                ix, iy = bbox_center(bbox(i))
                ry, rx = iy - cy, ix - cx
                # (nx, ny) = |rotation matrix| x (rx, ry)
                nx, ny = cosa * rx - sina * ry, sina * rx + cosa * ry
                dx, dy = nx - rx, ny - ry

                xy = coords(i)
                if len(xy) == 2:
                    x0, y0 = xy
                    coords(i, x0 + dx, y0 + dy)
                else:
                    x0, y0, x1, y1 = xy
                    coords(i, x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            elif isinstance(i, tuple):
                # item's points are rotated individually
                iid, first_coord, end = i
                c = coords(iid)
                if end is None:
                    end = len(c)
                lasty = end - 1

                # Coordinate range may start from y. But x is required to
                # compute rotation. So, align start index by x coordinate
                # boundary.
                start_idx = (first_coord >> 1) << 1

                citer = enumerate(c[start_idx:], start_idx)
                while True:
                    (xidx, x), (yidx, y) = next(citer), next(citer)

                    ry, rx = y - cy, x - cx
                    nx, ny = cosa * rx - sina * ry, sina * rx + cosa * ry
                    dx, dy = nx - rx, ny - ry

                    # unaligned ranges are possible
                    if first_coord >= xidx:
                        c[xidx] = x + dx
                    if yidx < end:
                        c[yidx] = y + dy

                    if yidx == lasty:
                        break

                coords(iid, *c)
            else:
                raise ValueError(
                    "Unsupported type of item: " + type(i).__name__
                )

    def scale(self, w, s, cx, cy):
        coords = w.coords
        bbox = w.bbox
        for i in self.items:
            if isinstance(i, integer_types):
                # only "center point" of item is scalled, item's points are
                # translated accordingly
                ix, iy = bbox_center(bbox(i))
                ry, rx = iy - cy, ix - cx
                # (nx, ny) = (rx, ry) * s
                nx, ny = rx * s, ry * s
                # translation is same for all the points
                dx, dy = nx - rx, ny - ry

                xy = coords(i)
                if len(xy) == 2:
                    x0, y0 = xy
                    coords(i, x0 + dx, y0 + dy)
                else:
                    x0, y0, x1, y1 = xy
                    coords(i, x0 + dx, y0 + dy, x1 + dx, y1 + dy)
            elif isinstance(i, tuple):
                # item's points are translated individually
                iid, first_coord, end = i
                c = coords(iid)
                if end is None:
                    end = len(c)
                for idx in range(first_coord, end):
                    if idx & 1:
                        ry = c[idx] - cy
                        ny = ry * s
                        c[idx] = cy + ny
                    else:
                        rx = c[idx] - cx
                        nx = rx * s
                        c[idx] = cx + nx
                coords(iid, *c)
            else:
                raise ValueError(
                    "Unsupported type of item: " + type(i).__name__
                )
