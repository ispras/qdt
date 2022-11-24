"""
sudo python3 -m pip install --upgrade pyopengl_accelerate
sudo apt install python3-opengl togl-demos
"""

from libe.graphics.gl import (
    GLArrays,
    gl_ready,
    GLSLProgram,
    identity4x4,
)

from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    glClear,
    glClearColor,
    glViewport,
)
from OpenGL.Tk import (
    Togl,
)
from six.moves.tkinter import (
    Frame,
)


a = GLArrays(
    vertices = [
        (0., 1.),
        (1., -.5),
        (-1., -.5),
    ],
    colors = [
        (1., 0., 0., 1.),
        (0., 1., 0., 1.),
        (0., 0., 1., 1.),
    ],
)


class OpenGL(Togl):

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


class OpenGLProbe(OpenGL):

    def __init__(self, **kw):
        bg = kw.pop("bg", (1., 1., 1., 1.))
        OpenGL.__init__(self, **kw)

        glClearColor(*bg)

    def __draw__(self):
        glClear(GL_COLOR_BUFFER_BIT)
        p.use(proj = identity4x4)
        a()
        self.swapbuffers()


b = OpenGLProbe()
root = b.master
f = Frame(root, width = 100, bg = "orange")
f.pack(side = "left", fill = "y")
b.pack(side = "right", expand = 1, fill = "both")

p = GLSLProgram(
"""
uniform mat4 proj;
varying vec4 color;
void main() {
    gl_Position = proj * gl_Vertex;
    color = gl_Color;
}
""",
"""
varying vec4 color;
void main() {
    gl_FragColor = color;
}
""",
)

root.mainloop()
