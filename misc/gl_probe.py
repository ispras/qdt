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

from OpenGL.Tk import (
    Opengl,
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


class OpenGLProbe(Opengl):

    def __init__(self, **kw):
        default = kw.setdefault
        default("height", 512)
        default("width", 512)

        bg = kw.pop("bg", (1., 1., 1.))
        Opengl.__init__(self, **kw)
        gl_ready()

        self.set_background(*bg)

    def basic_lighting(self):
        # disable superclass settings
        pass

    def redraw(self, *__, **___):
        a()


b = OpenGLProbe()
root = b.master
f = Frame(root, width = 100, bg = "orange")
f.pack(side = "left", fill = "y")
b.pack(side = "right", expand = 1, fill = "both")

GLSLProgram(
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
).use(
    proj = identity4x4,
)

root.mainloop()
