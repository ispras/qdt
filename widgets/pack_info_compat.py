from sys import (
    version_info as v
)

__all__ = [
    "pack_info"
]

try:
    from six.moves.tkinter import (
        _splitdict
    )
except ImportError:
    # compatibility with old Tkinter version
    # Copied from Tkinter 8.6 for Python 2.7.12
    def _splitdict(tk, v, cut_minus = True, conv = None):
        """Return a properly formatted dict built from Tcl list pairs.

        If cut_minus is True, the supposed '-' prefix will be removed from
        keys. If conv is specified, it is used to convert values.

        Tcl list is expected to contain an even number of elements.
        """
        t = tk.splitlist(v)
        if len(t) % 2:
            raise RuntimeError('Tcl list representing a dict is expected '
                               'to contain an even number of elements')
        it = iter(t)
        d = {}
        for key, value in zip(it, it):
            key = str(key)
            if cut_minus and key[0] == '-':
                key = key[1:]
            if conv:
                value = conv(value)
            d[key] = value
        return d

def pack_info_compat(widget):
    """Return information about the packing options
    for this widget."""
    d = _splitdict(widget.tk, str(widget.tk.call('pack', 'info', widget._w)))
    if 'in' in d:
        d['in'] = widget.nametowidget(d['in'])
    return d

if v[0] == 2:
    if v[1] > 7 or v[1] == 7 and v[2] >= 12:
        from Tkinter import (
            Pack
        )
        pack_info = Pack.pack_info
    else:
        pack_info = pack_info_compat

elif v[0] == 3:
    if v[1] > 3:
        from tkinter import (
            Pack
        )
        pack_info = Pack.pack_info
    else:
        pack_info = pack_info_compat
