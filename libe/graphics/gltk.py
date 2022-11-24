__all__ = [
    "OpenGLWidget"
]


from .gl import (
    gl_ready,
)

from OpenGL.Tk import (
    Togl,
)
from OpenGL.GL import (
    glViewport,
)


class OpenGLWidget(Togl):

    def __init__(self, *a, **kw):
        default = kw.setdefault
        default("height", 512)
        default("width", 512)

        Togl.__init__(self, *a, **kw)

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
