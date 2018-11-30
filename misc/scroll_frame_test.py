# base on
# https://stackoverflow.com/questions/16188420/python-tkinter-scrollbar-for-frame

from Tkinter import *


def data():
    for i in range(50):
       Label(frame, text = i).grid(row = i, column = 0)
       Label(frame, text = "my text" + str(i)).grid(row = i, column = 1)
       Label(frame, text = "..........").grid(row = i, column = 2)


def myfunction(event):
    canvas.configure(
        scrollregion = canvas.bbox("all"),
        width = 200,
        height = 200)


root = Tk()
sizex = 800
sizey = 600
posx = 100
posy = 100
root.wm_geometry("%dx%d+%d+%d" % (sizex, sizey, posx, posy))

root.grid()
root.rowconfigure(0, weight = 1)
root.columnconfigure(0, weight = 1)

myframe = Frame(root, relief = GROOVE, bd = 1)
myframe.grid(row = 0, column = 0, sticky = "NESW")

myframe.rowconfigure(0, weight = 1)
myframe.columnconfigure(0, weight = 1)
myframe.columnconfigure(1, weight = 0)

canvas = Canvas(myframe)
canvas.grid(row = 0, column = 0, sticky = "NESW")

frame = Frame(canvas)
myscrollbar = Scrollbar(myframe, orient = "vertical", command = canvas.yview)
myscrollbar.grid(row = 0, column = 1, sticky = "NESW")
canvas.configure(yscrollcommand = myscrollbar.set)

canvas.create_window((0, 0), window = frame, anchor = 'nw')
frame.bind("<Configure>", myfunction)
data()
root.mainloop()
