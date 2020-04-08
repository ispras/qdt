__all__ = [
    "HKGeneric"
      , "HKEntry"
      , "HKCombobox"
  , "HotKeyBinding"
  , "HotKey"
  , "KeyboardSettings"
]

# ML should be used there (instead of mlget) because the key will be modified
from common import (
    Persistent,
    mlget as _
)
from six.moves.tkinter import (
    SEL_FIRST,
    SEL_LAST,
    END,
    Entry
)
from six.moves.tkinter_ttk import (
    Combobox
)
from os.path import (
    dirname,
    join
)
from os import (
    name as os_name
)


class HKGeneric:

    def _on_ctrl_key_generic(self, event):
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
                self.delete(SEL_FIRST, SEL_LAST)


class HKEntry(Entry, HKGeneric):

    def __init__(self, *args, **kw):
        Entry.__init__(self, *args, **kw)

        self.bind("<Control-Key>", self._on_ctrl_key_generic)


class HKCombobox(Combobox, HKGeneric):

    def __init__(self, *a, **kw):
        Combobox.__init__(self, *a, **kw)

        self.bind("<Control-Key>", self._on_ctrl_key_generic, "+")


class HotKeyBinding(object):

    def __init__(self, callback, key_code,
        description = None,
        symbol = None
    ):
        self.cb = callback
        self.kc = key_code
        self.desc = description
        self.enabled = True
        self.symbol = symbol


class HotKey(object):
    def __init__(self, root):
        self.keys2bindings = {}
        self.keys2sym = {}
        self.cb2names = {}
        self.disabled = False

        root.bind_all("<Control-Key>", self.on_ctrl_key)
        root.bind_all("<<Control-Y-Breaked>>", self.on_ctrl_y_breaked)

        with KeyboardSettings() as kbd:
            self.code_translation = kbd.gen_translation_to_posix()

    def __call__(self, *a, **kw):
        self.add_binding(HotKeyBinding(*a, **kw))

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

        kc = self.code_translation.get(keycode, keycode)

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

        sym = binding.symbol
        if sym is not None:
            self.add_key_symbols({kc: sym})
        else:
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


KBD_STATE = join(dirname(__file__), "keyboard_settings.py")


class KeyboardSettings(Persistent):

    def __init__(self, file_name = KBD_STATE, **kw):
        super(KeyboardSettings, self).__init__(file_name, **kw)

    __var_base__ = lambda _ : "keyboard_settings"

    def gen_translation_to_posix(self, os = os_name):
        """ Accelerators (hotkeys) across entire GUI are given by posix/Tk key
codes. The translation generated by this function is a mapping containing only
differences between current OS/Tk implementation (or given by `os` argument)
and posix/Tk implementation.
        """
        if os == "posix":
            return {}

        try:
            current_codes = self.os_codes[os]
        except KeyError:
            # no special mapping
            return {}
        posix_codes = self.os_codes["posix"]

        mapping = {}
        for coord, key in current_codes.items():
            # `coord`inate of the keyboard key is an cross-platform invariant
            try:
                posix_key = posix_codes[coord]
            except KeyError:
                # no such code for that key index under POSIX
                continue
            # 0th index of a `key` descriptor is the OS specific key code
            mapping[key[0]] = posix_key[0]

        return mapping

