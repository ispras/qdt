from PyQt5.QtWidgets import (
    QFileDialog,
    QFontDialog,
    QColorDialog,
    QInputDialog,
    QLCDNumber,
    QLabel,
    QLineEdit,
    QTextEdit,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QMenu,
    QAction,
    QApplication,
    QMainWindow,
    QToolTip,
    QPushButton,
    QMessageBox,
    QDesktopWidget,
    QSlider,
)
from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
)
from PyQt5.QtGui import (
    QIcon,
    QFont,
)
from sys import (
    argv,
)
from os.path import (
    join,
    dirname as p, # parent
    abspath,
)


class Example(QMainWindow):
    """ An example of working with Qt5 Python bindings.

Based on: http://zetcode.com/gui/pyqt5/firstprograms/
    """

    def __init__(self):
        super().__init__()
        self.init_UI()

    def init_UI(self):
        self.setToolTip("This is an <b>Example</b> <code>%s</code>" % (
            type(self).__base__.__name__
        ))

        # button examples
        bt = QPushButton("Button", self)
        bt.setToolTip("This is a <b>QPushButton</b> widget")
        bt.resize(bt.sizeHint())
        # Absolute layout
        bt.move(30, 70)

        bt_quit = QPushButton("Quit", self)
        bt_quit.clicked.connect(self.close)
        # Note, using `QApplication.instance().exit` instead of `self.close`
        # bypassing close confirmation dialog by `closeEvent`.

        bt_quit.resize(bt.sizeHint())
        # Absolute layout
        bt_quit.move(30, 100)

        # Auto layout
        # Linear layout
        pane = QWidget(self)
        pane.move(120, 70)
        pane.resize(100, 100)

        bt_ok = QPushButton("OK")
        bt_cancel = QPushButton("Cancel")

        hbox = QHBoxLayout()
        hbox.addStretch(1) # space to the left of buttons
        hbox.addWidget(bt_ok)
        hbox.addWidget(bt_cancel)

        vbox = QVBoxLayout()
        vbox.addStretch(1) # space to the up of buttons row
        vbox.addLayout(hbox)

        pane.setLayout(vbox)

        # Grid layout
        grid_pane = QWidget(self)
        grid_pane.move(30, 160)
        grid_pane.resize(300, 230)

        grid = QGridLayout()
        grid_pane.setLayout(grid)

        grid.setSpacing(2)

        names = [
            "Cls", "Bck",  "", "Close",
              "7",   "8", "9",     "/",
              "4",   "5", "6",     "*",
              "1",   "2", "3",     "-",
              "0",   ".", "=",     "+",
        ]

        num_row = 3

        positions = [
            (i, j) for i in range(num_row, num_row + 5) for j in range(4)
        ]

        for position, name in zip(positions, names):
            if name == "":
                continue
            bt_num = QPushButton(name, grid_pane)
            grid.addWidget(bt_num, *position) # args: widget, row, column

        lb_res = QLabel("Result")
        # args: widget, row, column, row span, column span
        grid.addWidget(lb_res, 0, 0, 1, 1)

        le_mem = QLineEdit("Mem")
        grid.addWidget(le_mem, 1, 0)

        self.te_res = te_res = QTextEdit("0")
        grid.addWidget(te_res, 0, 1, num_row, 3)

        # Window appearance configuration
        self.resize(500, 400)
        self.center()
        self.setWindowTitle("Icon")
        icon_path = join(p(p(abspath(__file__))), "widgets", "logo.png")
        self.setWindowIcon(QIcon(icon_path))

        # Status bar example
        self.statusBar().showMessage("Ready")

        # Menu bar example
        menubar = self.menuBar()

        m_file = menubar.addMenu("&File")

        exit_png = join(p(abspath(__file__)), "exit.png")
        a_exit = QAction(QIcon(exit_png), "&Exit", self)
        a_exit.setShortcut("Ctrl+Q")
        a_exit.setStatusTip("Exit application")
        a_exit.triggered.connect(self.close)
        m_file.addAction(a_exit)

        a_new = QAction("New", self)
        m_file.addAction(a_new)

        m_import = QMenu("Import", self)
        m_file.addMenu(m_import)

        # + QFileDialog example
        a_open = QAction("Open", self)
        a_open.setShortcut("Ctrl+O")
        a_open.setStatusTip("Open a file")
        a_open.triggered.connect(self._on_open)
        m_file.addAction(a_open)

        a_import = QAction("Import mail", self)
        m_import.addAction(a_import)

        m_view = menubar.addMenu("View")

        a_status_bar = QAction("Show status bar", self, checkable = True)
        a_status_bar.setStatusTip("Toggle status bar showing")
        a_status_bar.setChecked(True)
        a_status_bar.triggered.connect(self._on_status_bar)

        m_view.addAction(a_status_bar)

        # Context menu (popup) example
        self.c_menu = c_menu = QMenu(self)
        c_menu.addAction(a_new)
        a_open = c_menu.addAction("Open")
        c_menu.addAction(a_exit)

        # Tool bar example
        toolbar = self.addToolBar("Exit")
        toolbar.addAction(a_exit)

        # signals and events example
        lcd_pane = QWidget(self)
        lcd_pane.move(300, 70)
        lcd_pane.resize(100, 100)
        slider_vbox = QVBoxLayout()
        lcd_pane.setLayout(slider_vbox)

        lcd = QLCDNumber(self)
        sld = QSlider(Qt.Horizontal, self)

        slider_vbox.addWidget(lcd)
        slider_vbox.addWidget(sld)

        # valueChanged is a signal. lcd.display is used in slot, it handles
        # signals.

        def trace_signal(s):
            te_res.append(repr(s))
            lcd.display(s)

        sld.valueChanged.connect(trace_signal)

        # Mouse events
        self.setMouseTracking(True) # enables mouseMoveEvent

        # Getting sender of an event
        for b in [bt, bt_ok, bt_cancel]:
            b.clicked.connect(self._button_clicked)

        # handlers for self defined signals
        self.close_wnd.connect(self.close)

        # dialog example
        self.bt_dialog = bt_dialog = QPushButton("Dialog", self)
        bt_dialog.move(150, 70)
        bt_dialog.clicked.connect(self._show_dialog)

    # Self defined signals, it's a class attribute
    close_wnd = pyqtSignal()

    def mousePressEvent(self, __):
        self.close_wnd.emit()

    # Standard handlers
    # Define a method with a specific name to catch the event.

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()

        text = "x: {0},  y: {1}".format(x, y)

        self.statusBar().showMessage(text)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        reply = QMessageBox.question(self, "Message", "Are you sure to quit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def contextMenuEvent(self, event):
        a = self.c_menu.exec_(self.mapToGlobal(event.pos()))

    # Custom event handlers

    def _button_clicked(self):
        sender = self.sender()
        self.te_res.append(repr(sender))

    def _on_status_bar(self, state):
        if state:
            self.statusBar().show()
        else:
            self.statusBar().hide()

    def _show_dialog(self):
        text, ok = QInputDialog.getText(self, "Input Dialog",
            "Enter your name:"
        )
        if ok:
            self.te_res.append("Hi, %s" % text)

        # XXX: warning:
        # GtkDialog mapped without a transient parent. This is discouraged.
        color = QColorDialog.getColor(parent = self)
        if color.isValid():
            self.bt_dialog.setStyleSheet("QWidget { background-color: %s }" % (
                color.name()
            ))

        # XXX: warning:
        # GtkDialog mapped without a transient parent. This is discouraged.
        font, font_ok = QFontDialog.getFont(parent = self)
        if font_ok:
            self.te_res.setFont(font)

    def _on_open(self):
        fname = QFileDialog.getOpenFileName(self, "Open file", __file__)

        if fname[0]:
            with open(fname[0], "r") as f:
                data = f.read()

            self.te_res.setText(data)

    # helpers

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


def main():
    app = QApplication(argv)

    QToolTip.setFont(QFont("SansSerif", 10))

    w = Example()
    w.show()

    return app.exec_()


if __name__ == "__main__":
    exit(main() or 0)
