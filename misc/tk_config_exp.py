from six.moves.tkinter import (
    Tk,
)
from pprint import (
    pprint,
)
from traceback import (
    print_exc,
)

root = Tk()
pprint(root.config())
pprint(root.config("bg"))
pprint(root.config(cnf = "bg"))
pprint(root.config(cnf = {"bg" : '#FF0000'}))
pprint(root.config(bg = '#FF0000'))
pprint(root.config(bg = '#FF0000', padx = 10))
pprint(root.config(cnf = {"bg" : "#00FF00"}, bg = "#FF0000"))
try:
    pprint(root.config(cnf = "bg", bg = "#FF0000"))
except:
    print_exc()
try:
    pprint(root.config("bg", bg = "#FF0000"))
except:
    print_exc()

root.mainloop()
