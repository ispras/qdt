"""
sudo python3 -m pip install --upgrade pyopengl_accelerate
sudo apt install python3-opengl togl-demos
"""

from common import (
    flatten,
)
from libe.graphics.gl import (
    create_shader,
    create_gls_program,
)

from ctypes import (
    c_float,
    c_uint16,
    c_void_p,
    sizeof,
)
from OpenGL.Tk import (
    Opengl,
)
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    glBindBuffer,
    glBufferData,
    GL_COLOR_ARRAY,
    glColorPointer,
    # glDisableClientState,
    glDrawElements,
    GL_DYNAMIC_DRAW,
    GL_ELEMENT_ARRAY_BUFFER,
    glEnableClientState,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    glGenBuffers,
    # GL_NORMAL_ARRAY,
    GL_TRIANGLES,
    # GL_TEXTURE_COORD_ARRAY,
    GL_UNSIGNED_SHORT,
    glUseProgram,
    GL_VERTEX_ARRAY,
    glVertexPointer,
    GL_VERTEX_SHADER,
)
from six.moves.tkinter import (
    Frame,
)


class OpenGLProbe(Opengl):

    def __init__(self, **kw):
        default = kw.setdefault
        default("height", 512)
        default("width", 512)

        bg = kw.pop("bg", (1., 1., 1.))
        Opengl.__init__(self, **kw)

        self.set_background(*bg)

    def basic_lighting(self):
        # disable superclass settings
        pass

    def redraw(self, *__, **___):
        global elements_n
        glDrawElements(GL_TRIANGLES, elements_n, GL_UNSIGNED_SHORT, None)


b = OpenGLProbe()
root = b.master
f = Frame(root, width = 100, bg = "orange")
f.pack(side = "left", fill = "y")
b.pack(side = "right", expand = 1, fill = "both")

v_shader_code = """
varying vec4 color;
void main() {
    gl_Position = gl_Vertex;
    color = gl_Color;
}
"""
f_shader = """
varying vec4 color;
void main() {
    gl_FragColor = color;
}
"""


v_shader = create_shader(v_shader_code, GL_VERTEX_SHADER)
f_shader = create_shader(f_shader, GL_FRAGMENT_SHADER)
glsp_0 = create_gls_program(v_shader, f_shader)

glUseProgram(glsp_0)

vertices = [
    (0., 1.),
    (1., -.5),
    (-1., -.5),
]
colors = [
    (1., 0., 0., 1.),
    (0., 1., 0., 1.),
    (0., 0., 1., 1.),
]
indices = [
    0, 1, 2,
]
elements_n = min(len(vertices), len(colors))

vertex_data = list(flatten(zip(vertices, colors)))
vertex_array = (c_float * len(vertex_data))(*vertex_data)

vao, eao = glGenBuffers(2)

glBindBuffer(GL_ARRAY_BUFFER, vao)
glBufferData(GL_ARRAY_BUFFER, vertex_array, GL_DYNAMIC_DRAW)
glBindBuffer(GL_ARRAY_BUFFER, 0)

element_array = (c_uint16 * len(indices))(*indices)

glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, eao)
glBufferData(GL_ELEMENT_ARRAY_BUFFER, element_array, GL_DYNAMIC_DRAW)
glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

glEnableClientState(GL_VERTEX_ARRAY)
glEnableClientState(GL_COLOR_ARRAY)
# glDisableClientState(GL_TEXTURE_COORD_ARRAY)
# glDisableClientState(GL_NORMAL_ARRAY)

glBindBuffer(GL_ARRAY_BUFFER, vao)

vertex_len = len(vertices[0])
color_len = len(colors[0])

stride = sizeof(c_float) * (vertex_len + color_len)

glVertexPointer(vertex_len, GL_FLOAT, stride, None)
glColorPointer(color_len, GL_FLOAT, stride,
    c_void_p(vertex_len * sizeof(c_float))
)

glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, eao)

root.mainloop()
