from widgets import (
    Chainview,
    GUITk,
)


root = GUITk()
v0 = Chainview(root)
v0.pack()
v1 = Chainview(root)
v1.pack()
v2 = Chainview(root)
v2.pack()
v3 = Chainview(root)
v3.pack()

v1.config(chain = ("0", "1", "2", "3"))
v2.config(chain = ("0", "1", "2"))
assert len(v2.winfo_children()) == 3

v2.config(index = 3)
v2.config(chain = ("0", "1", "2", "3", "4", "5"))

v3.config(index = 10)
v3.config(chain = ("0", "1", "2", "3", "4"))

def on_v_select(e):
    w = e.widget
    print("%r: %s" % (w, w.cget("subchain")))

for v in root.winfo_children():
    v.bind(Chainview.EVENT_SELECT, on_v_select)

root.mainloop()
