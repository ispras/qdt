#!/usr/bin/python2

from six.moves.tkinter import \
    StringVar, \
    Tk

from widgets import \
    VarTreeview

class Mytest(object):
    def __init__(self, delay, var1, var2):
        self.delay, self.var1, self.var2 = delay, var1, var2

    def test_begin(self, root):
        self.root = root
        root.after(self.delay, self.on_after_cb)

    def on_after_cb(self):
        d = self.var1.get()
        self.var1.set(self.var2.get())
        self.var2.set(d)

        self.root.after(self.delay, self.on_after_cb)

def main():
    root = Tk()
    root.title("Test VarTreeview")

    device_tree = VarTreeview(root)
    device_tree["columns"] = ("Macros")

    dev = StringVar()
    macro = StringVar()
    dev.set("Devices")
    macro.set("Macros")

    device_tree.heading("#0", text = dev)
    device_tree.heading("Macros", text = macro)

    device_tree.grid(sticky = "NEWS")

    test = Mytest(600, dev, macro)
    test.test_begin(root)

    root.mainloop()

if __name__ == '__main__':
    main()
