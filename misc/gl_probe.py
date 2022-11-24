"""
sudo python3 -m pip install --upgrade pyopengl_accelerate
sudo apt install python3-opengl togl-demos
"""

from libe.graphics.gl import (
    GLArrays,
    GLSLProgram,
    identity4x4,
)
from libe.graphics.gltk import (
    OpenGLWidget,
)

from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    glClear,
    glClearColor,
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


class OpenGLProbe(OpenGLWidget):

    def __init__(self, **kw):
        bg = kw.pop("bg", (1., 1., 1., 1.))
        OpenGLWidget.__init__(self, **kw)

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
