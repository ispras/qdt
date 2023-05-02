__all__ = [
    "OpenGLWidget"
]


from .gl import (
    gl_ready,
)

from OpenGL.Tk import (
    __file__ as OpenGL_Tk___file__,
    _default_root as OpenGL_Tk__default_root,
    Togl,
)
from OpenGL.GL import (
    glViewport,
)
from os.path import (
    dirname,
    join,
)
from six.moves.tkinter import (
    Frame,
)
from sys import (
    maxsize,
    platform,
)


def init_togl(master):
    if master is None:
        # use any widget, as lightweight as possible, to get implicitly
        # created `Tk` (e.g. _default_root)
        f = Frame()
        tk = f.master.tk
        f.destroy()
    else:
        tk = master.tk

    # check if togl is already loaded into current tk
    ret = tk.call("info", "commands", "togl")
    if "togl" in ret:
        return

    # don't need second Tk instance
    assert tk is not OpenGL_Tk__default_root.tk
    OpenGL_Tk__default_root.destroy()

    # This code is based on `OpenGL.Tk` implementation.
    # This implementation allow `Togl` to work with any `Tk` instance, not only
    # with the one internally created by `OpenGL.Tk.__init__` script.

    if maxsize > 2 ** 32:
        suffix = "-64"
    else:
        suffix = ""

    TOGL_DLL_PATH = join(
        dirname(OpenGL_Tk___file__),
        "togl-" + platform + suffix,
    )

    tk.call("lappend", "auto_path", TOGL_DLL_PATH)
    try:
        tk.call('package','require','Togl')
        tk.eval('load {} Togl')
    except:
        print("hint: on Debian systems this is provided by `libtogl2`")
        raise


class OpenGLWidget(Togl):

    def __init__(self, master = None, *a, **kw):
        default = kw.setdefault
        default("height", 512)
        default("width", 512)

        init_togl(master)

        Togl.__init__(self, master, *a, **kw)

        self._do_validate = self._do_validate_first
        self._do_invalidate_id = None
        self._set_viewport = True

        self.bind("<Map>", self._on_map, "+")
        self.bind("<Expose>", self._on_expose, "+")
        self.bind("<Configure>", self._on_configure, "+")
        self.bind("<Destroy>", self._on_destroy, "+")

    def invalidate(self):
        if self._do_invalidate_id is None:
            self._do_invalidate_id = self.after(1, self._do_validate)

    def _do_validate(self):
        self._do_invalidate_id = None
        self.__validate__()

    def _do_validate_first(self):
        del self._do_validate
        self.makecurrent()

        # XXX: still can't work with multiple contexts
        # XXX: each widget has its own context
        gl_ready()

        self._do_validate()

    def _on_destroy(self, __):
        id_ = self._do_invalidate_id
        if id_ is not None:
            self._do_invalidate_id = None
            self.after_cancel(id_)

    def _on_map(self, __):
        self.invalidate()

    def _on_expose(self, __):
        self.invalidate()

    def _on_configure(self, __):
        self._set_viewport = True
        self.invalidate()

    def __validate__(self):
        self.makecurrent()
        if self._set_viewport:
            self._set_viewport = False
            glViewport(0, 0, self.winfo_width(), self.winfo_height())
        self.__draw__()

    def __draw__(self):
        pass
