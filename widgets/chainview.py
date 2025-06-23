__all__ = [
    "Chainview"
]

from .gui_frame import (
    GUIFrame,
)
from .tk_config_override_helper import (
    TkConfigureOverrideHelper,
)

from six.moves import (
    zip_longest,
)
from six.moves.tkinter import (
    Button,
    LEFT,
    RAISED,
    SUNKEN,
    Y,
)


class Chainview(TkConfigureOverrideHelper, GUIFrame):
    """ Series of buttons. None or one of them could be selected.
    """

    EVENT_SELECT = "<<ChainviewSelect>>"

    __extra_cnfigure_options__ = (
        "chain",            # rw
        "index",            # rw
        "selected",         # r
        "subchain",         # r
        "EVENT_SELECT",     # rw
        "side"              # r  # TODO: rw
        "expand"            # r  # TODO: rw
    )

    def __init__(self, *a, **kw):
        GUIFrame.__init__(self, *a, **kw)

        # TODO: it's a generic feature, outline to a helper class
        self._cache = []  # of previosuly used buttons

    _chain = ()

    @property
    def chain(self):
        return self._chain

    @staticmethod
    def _bt_activate(bt):
        bt.configure(relief = SUNKEN)

    @staticmethod
    def _bt_normalize(bt):
        bt.configure(relief = RAISED)

    @chain.setter
    def chain(self, chain):
        if self._chain == chain:
            return
        self._chain = chain = tuple(chain)

        children = self.pack_slaves()

        prev = self._index
        if prev > 0:
            self._bt_normalize(children[prev - 1])

        index = self._next_index
        if index < 0:
            index = len(chain) + index + 1

        index = max(0, min(len(chain), index))
        self._index = index

        cache = self._cache
        side = self._side
        expand = self._expand
        for bt, i_part in zip_longest(children, enumerate(chain, 1)):
            if i_part is None:
                bt.pack_forget()
                self._cache.append(bt)
                continue
            (i, part) = i_part
            if bt is None:
                try:
                    bt = cache.pop()
                except IndexError:
                    bt = Button(self)
                bt.pack(side = side, fill = Y, expand = expand)

            bt.configure(
                command = lambda _i = i: self._on_bt(_i),
                text = part,
            )
            if i == index:
                self._bt_activate(bt)

    def _on_bt(self, i):
        if i == self._index:
            # unselect
            self.index = 0
        else:
            self.index = i

    _index = 0
    # During a common `configure` call `index` can be handled before `chain`.
    # Hence, it must be remembered because public index is truncated to
    # current `chain` limits.
    _next_index = -1

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, index):
        index = int(index)
        self._next_index = index
        if self._index == index:
            return
        children = self.pack_slaves()
        prev = self._index
        if prev > 0:
            self._bt_normalize(children[prev - 1])
        if index < 0:
            index = len(children) - index + 1
        index = max(0, min(len(children), index))
        if index > 0:
            self._bt_activate(children[index - 1])
        self._index = index
        self.event_generate(self.EVENT_SELECT)

    @property
    def subchain(self):
        return self._chain[:self._index]

    @property
    def selected(self):
        index = self._index
        if index:
            return self._chain[index - 1]
        return None

    _side = LEFT

    @property
    def side(self):
        return self._side

    @side.setter
    def side(self, side):
        # TODO: remember `side` and re-`pack` buttons
        raise NotImplementedError

    _expand = False

    @property
    def expand(self):
        return self._expand

    @expand.setter
    def expand(self, expand):
        # TODO: remember `expand` and re-`pack` buttons
        raise NotImplementedError
