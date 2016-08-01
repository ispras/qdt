from common import \
    ML as _

from Tkinter import \
    Entry

class HKEntry(Entry):
    def __init__(self, *args, **kw):
        Entry.__init__(self, *args, **kw)

        self.bind("<Control-Key>", self.ignore)

    def ignore(self, event):
        if event.keycode == 29: # prevent paste on Ctrl + Y
            return "break"

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

        root.bind_all("<Control-Key>", self.on_ctrl_key)

    def on_ctrl_key(self, event):
        kc = event.keycode

        if not (kc in self.keys2sym and self.keys2sym[kc] == event.keysym):
            self.keys2sym[kc] = event.keysym
            if kc in self.keys2bindings:
                for kb in self.keys2bindings[kc]:
                    self.update_name(kb)

        if not kc in self.keys2bindings:
            return

        kbs = self.keys2bindings[kc]
        for kb in kbs:
            if kb.enabled:
                kb.cb()

    def add_binding(self, binding):
        kc = binding.kc
        if kc in self.keys2bindings:
            self.keys2bindings[kc].append(binding)
        else:
            self.keys2bindings[kc] = [binding]

        self.update_name(binding)

    def add_bindings(self, bindings):
        for b in bindings:
            self.add_binding(b)

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
