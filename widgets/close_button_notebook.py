from six.moves.tkinter_ttk import \
    Notebook, \
    Style

from six.moves.tkinter import \
    PhotoImage

"""
The code is based on
 http://stackoverflow.com/a/39459376
or
 http://stackoverflow.com/questions/39458337/is-there-a-way-to-add-close-buttons-to-tabs-in-tkinter-ttk-notebook
"""

class CloseButtonNotebook(Notebook):
    """A ttk Notebook with close buttons on each tab"""

    def __init__(self, *args, **kwargs):
        if not CloseButtonNotebook.initialized:
            CloseButtonNotebook.initialize_style()
            CloseButtonNotebook.initialized = True

        kwargs["style"] = "CloseButtonNotebook"
        Notebook.__init__(self, *args, **kwargs)

        self._active = None

        self.bind("<ButtonPress-1>", self.on_close_press, True)
        self.bind("<ButtonRelease-1>", self.on_close_release)

    def on_close_press(self, event):
        """Called when the button is pressed over the close button"""

        element = self.identify(event.x, event.y)

        if "close" in element:
            index = self.index("@%d,%d" % (event.x, event.y))
            self.state(['pressed'])
            self._active = index

    def on_close_release(self, event):
        """Called when the button is released over the close button"""
        if not self.instate(['pressed']):
            return

        element =  self.identify(event.x, event.y)
        index = self.index("@%d,%d" % (event.x, event.y))

        if "close" in element and self._active == index:
            self.forget(index)
            self.event_generate("<<NotebookTabClosed>>")

        self.state(["!pressed"])
        self._active = None


    initialized = False

    @staticmethod
    def initialize_style():
        style = Style()
        global images
        images = (
            PhotoImage("img_close", data='''
                R0lGODlhCAAIAMIBAAAAADs7O4+Pj9nZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                5kEJADs=
                '''),
            PhotoImage("img_closeactive", data='''
                R0lGODlhCAAIAMIEAAAAAP/SAP/bNNnZ2cbGxsbGxsbGxsbGxiH5BAEKAAQALAAA
                AAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU5kEJADs=
                '''),
            PhotoImage("img_closepressed", data='''
                R0lGODlhCAAIAMIEAAAAAOUqKv9mZtnZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                5kEJADs=
            ''')
        )
    
        style.element_create("close", "image", "img_close",
            ("active", "pressed", "!disabled", "img_closepressed"),
            ("active", "!disabled", "img_closeactive"),
            border = 8,
            sticky = ''
        )
        style.layout("CloseButtonNotebook",
            [("CloseButtonNotebook.client", {"sticky": "nswe"})]
        )
        style.layout("CloseButtonNotebook.Tab",
[
    ("CloseButtonNotebook.tab", {
        "sticky": "NEWS", 
        "children": [
            ("CloseButtonNotebook.padding", {
                "side": "top", 
                "sticky": "NEWS",
                "children": [
                    ("CloseButtonNotebook.focus",
{
    "side": "top", 
    "sticky": "NEWS",
    "children": [
        ("CloseButtonNotebook.label", {"side": "left", "sticky": ''}),
        ("CloseButtonNotebook.close", {"side": "left", "sticky": ''}),
    ]
}
                    )
                ]
            })
        ]
    })
]
    )
