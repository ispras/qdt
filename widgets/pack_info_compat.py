from sys import \
    version_info as v

__all__ = ["pack_info"]

def pack_info_compat(widget):
    """Return information about the packing options
    for this widget."""
    d = _splitdict(widget.tk, widget.tk.call('pack', 'info', widget._w))
    if 'in' in d:
        d['in'] = widget.nametowidget(d['in'])
    return d

if v[0] == 2:
    if v[1] > 7 or v[1] == 7 and v[2] >= 12:
        from Tkinter import Pack
        pack_info = Pack.pack_info
    else:
        from Tkinter import _splitdict
        pack_info = pack_info_compat

elif v[0] == 3:
    if v[1] > 3:
        from tkinter import Pack
        pack_info = Pack.pack_info
    else:
        from tkinter import _splitdict
        pack_info = pack_info_compat
