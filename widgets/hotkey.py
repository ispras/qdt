# ML should be used there (instead of mlget) because the key will be modified
from common import \
    mlget as _

from six.moves.tkinter import \
    END, \
    Entry

class HKEntry(Entry):
    def __init__(self, *args, **kw):
        Entry.__init__(self, *args, **kw)

        self.bind("<Control-Key>", self.ignore)

    def ignore(self, event):
        if event.keycode == 29: # prevent paste on Ctrl + Y
            self.event_generate("<<Control-Y-Breaked>>")
            return "break"
        elif event.keycode == 38: # Ctrl-A: select all
            self.selection_range(0, END)
            # No more actions may perform
            return "break"
        elif event.keycode == 55: # Ctrl-V: insert text from buffer
            if self.select_present():
                # Remove a selected text during insertion. It is equivalent
                # to replacement of a selected text with the text being
                # inserted, because the insertion cursor cannot be outside a
                # selected text.
                self.delete("sel.first", "sel.last")

class HotKeyBinding(object):
    def __init__(self, callback, key_code, description = None):
        self.cb = callback
        self.kc = key_code
        self.desc = description
        self.enabled = True

class HotKey(object):
    def __init__(self, root):
        self.keys2bindings = {}
        self.keys2sym = {}
        self.cb2names = {}
        self.disabled = False

        root.bind_all("<Control-Key>", self.on_ctrl_key)
        root.bind_all("<<Control-Y-Breaked>>", self.on_ctrl_y_breaked)

    def add_key_symbols(self, keys2sym):
        for key, sym in keys2sym.items():
            self.keys2sym[key] = sym

            try:
                bindings = self.keys2bindings[key]
            except KeyError:
                continue

            for binding in bindings:
                self.update_name(binding)

    def process_ctrl_key(self, keycode, keysym):
        if self.disabled:
            return

        kc = keycode

        if not (kc in self.keys2sym and self.keys2sym[kc] == keysym):
            self.keys2sym[kc] = keysym
            if kc in self.keys2bindings:
                for kb in self.keys2bindings[kc]:
                    self.update_name(kb)

        if not kc in self.keys2bindings:
            return

        kbs = self.keys2bindings[kc]
        for kb in kbs:
            if kb.enabled:
                kb.cb()

    def on_ctrl_y_breaked(self, event):
        self.process_ctrl_key(29, 'Y')

    def on_ctrl_key(self, event):
        self.process_ctrl_key(event.keycode, event.keysym)

    def add_binding(self, binding):
        kc = binding.kc
        self.keys2bindings.setdefault(kc, []).append(binding)

        self.update_name(binding)

    def add_bindings(self, bindings):
        for b in bindings:
            self.add_binding(b)

    def delete_binding(self, binding):
        kc = binding.kc
        self.keys2bindings[kc].remove(binding)

    def delete_bindings(self, bindings):
        for b in bindings:
            self.delete_binding(b)

    def get_keycode_string(self, callback):
        if callback in self.cb2names:
            return self.cb2names[callback]
        else:
            string = _("Unassigned")
            self.cb2names[callback] = string
            return string

    def set_enabled(self, callback, enabled = True):
        for kbs in self.keys2bindings.values():
            for kb in kbs:
                if kb.cb == callback:
                    kb.enabled = enabled

    def update_name(self, binding):
        keycode = binding.kc
        if keycode in self.keys2sym:
            name = "Ctrl+" + self.keys2sym[keycode]
        else:
            name = "Ctrl+[" + str(keycode) + "]"

        cb = binding.cb
        if cb in self.cb2names:
            self.cb2names[cb].set(name)
        else:
            self.cb2names[cb] = _(name)

    def disable_hotkeys(self):
        self.disabled = True

    def enable_hotkeys(self):
        self.disabled = False
