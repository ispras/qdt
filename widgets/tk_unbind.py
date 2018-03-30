__all__ = [
    "unbind"
]

def unbind(tk_widget, sequence, funcid = None):
    if funcid is None:
        tk_widget.tk.call('bind', tk_widget._w, sequence, '')
    else:
        binded = tk_widget.tk.call("bind", tk_widget._w, sequence)

        new_binded = '\n'.join([ s for s in binded.split('\n')
                             if s and not funcid in s ]) + '\n'

        tk_widget.tk.call("bind", tk_widget._w, sequence, new_binded)

        tk_widget.deletecommand(funcid)
