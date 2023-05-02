from common import (
    bind_all_mouse_wheel,
    lazy,
)
from libe.graphics.gl import (
    GLArrays,
    GLSLProgram,
    identity4x4,
    ortho4x4,
)
from libe.graphics.gltk import (
    OpenGLWidget,
)

from copy import (
    deepcopy,
)
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_LINE_LOOP,
    GL_RGBA8,
    GL_TEXTURE_2D,
    glBindTexture,
    glClear,
    glClearColor,
    glColor3f,
    glGenTextures,
    glTexImage2D,
)
from six.moves.tkinter import (
    BOTH,
    Tk,
)


sign = lambda x: (-1 if x < 0 else 1) if x else 0


class Block:

    def __init__(self, aabb = (0, 0, 0, 0)):
        self._aabb = aabb  # geometric Y-axis
        self._parent = None
        self._children = []

        self._update_children_aabb()

    @lazy
    def width(self):
        l, __, r, __ = self._aabb
        return r - l

    @lazy
    def height(self):
        __, t, __, b = self._aabb
        return t - b

    def _update_children_aabb(self):
        l = 0
        r = 0
        t = 0
        b = 0
        for c in self._children:
            bl, bt, br, bb = c._aabb
            if bl < l:
                l = bl
            if r < br:
                r = br
            if t < bt:
                t = bt
            if bb < b:
                b = bb
        self._children_aabb = l, t, r, b

    def add_child(self, b):
        b._parent = self
        self._children.append(b)
        self._update_children_aabb()

    def resize(self, aabb):
        self._aabb = aabb
        if self._parent:
            self._parent._update_children_aabb()


class GLContext:

    def __init__(self):
        self._textures = {}


class GLTexture:

    def __init__(self, ctx):
        self._id = _id = glGenTextures(1)
        ctx._textures[_id] = self
        self._size = None

    def gen_buffer(self, size):
        self._size = size

        glBindTexture(self._id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, size[0], size[1], 0, 0, 0, 0)


class BlockView:

    def __init__(self, block):
        self._block = block
        self._children = list(map(BlockView, block._children))

    def iter_gl_arrays(self):
        return self._iter_gl_arrays(0., 0., 1.)

    def _iter_gl_arrays(self,
        x, y,  # offset
        s,  # scale
    ):
        block = self._block

        l, t, r, b = block._aabb

        w = r - l
        h = t - b

        if not (w and h):
            return

        x += l * s
        y += b * s

        a = GLArrays(
            vertices = (
                # CCW
                (x        , y + h * s),
                (x        , y        ),
                (x + w * s, y        ),
                (x + w * s, y + h * s),
            ),
            what = GL_LINE_LOOP,
        )
        a._block_view = self
        yield a

        cl, ct, cr, cb = block._children_aabb

        cw = cr - cl
        ch = ct - cb

        if not (cw and ch):
            return

        # scale children to fit aabb
        ws = w / cw
        hs = h / ch

        if ws < hs:
            cs = s * ws
            y += abs(ch * cs - h * s) * 0.5
        else:
            cs = s * hs
            x += abs(cw * cs - w * s) * 0.5

        for cv in self._children:
            for b in cv._iter_gl_arrays(x, y, cs):
                yield b


p = GLSLProgram(
"""
varying vec4 color;

uniform mat4 P;
uniform vec2 offset;
uniform float scale;

void main() {
    gl_Position = P * vec4(gl_Vertex.xy * scale + offset, 0., 1.);
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


class TkEventBindHelper:

    def bind_all_handlers(self):
        for n in dir(self):
            if not n.startswith("_on_tk_"):
                continue
            f = getattr(self, n)
            event = f.__doc__
            if event is None:
                event = n[7:].replace('_', '-')
            if event[0] != '<':
                event = '<' + event + '>'
            self.bind(event, f, "+")


class ST_NORMAL: pass
class ST_CHANGE_OFFSET: pass

class WBlocks(OpenGLWidget, TkEventBindHelper):

    def __init__(self, master,
            block = Block(),
            bg = (0., 0., 0., 1.),
            scale_step = 1.1,
            **kw
        ):
        OpenGLWidget.__init__(self, master, **kw)

        self.scale_step = scale_step

        self._state = ST_NORMAL
        self._P = identity4x4

        self.bind_all_handlers()
        bind_all_mouse_wheel(self, self._on_whell, "+")

        glClearColor(*bg)
        self.set_block(block)

    def _on_whell(self, e):
        d = e.delta
        s = self._scale

        # scale factor
        sf = self.scale_step ** d

        # new scale
        ns = s * sf

        self.set_scale(ns)

        w = self.winfo_width()
        h = self.winfo_height()

        # window size scale
        ws = min(w, h)

        if not ws:
            return

        ox, oy = self._offset

        x = e.x
        y = e.y

        cx = w / 2.
        cy = h / 2.

        crx = 2 * (x - cx) / ws
        cry = 2 * (cy - y) / ws

        """
        # center-relative scaled
        crsx = crx / s
        crsy = cry / s

        # position of cursor
        px = -ox / s + crsx
        py = -oy / s + crsy

        # position of cursor with new scale if nothing moved
        npx = -ox / ns + crx / ns
        npy = -oy / ns + cry / ns

        print("p", px, py)
        print("np", npx, npy)

        # Need p == np.
        # I.e. cursor should be over same point block after scale
        # change.

        # Getting new offset: nox, noy.
        #     -ox / s + crx / s == -nox / sn + crx / sn
        # Note, crx, cry does not chenge.
        #     (-ox + crx) / s == (-nox + crx) / sn
        #     (-ox + crx) * sn / s == -nox + crx
        # Note, sn / s = sf, see above.
        #     (-ox + crx) * sf - crx == -nox
        #     -nox == (-ox + crx) * sf - crx
        #     nox == crx - (-ox + crx) * sf
        #     nox = crx + (ox - crx) * sf
        # The same is for noy.
        """

        self.set_offset((
            crx + (ox - crx) * sf,
            cry + (oy - cry) * sf,
        ))

    def _on_tk_2(self, e):
        if self._state is ST_NORMAL:
            self._x0 = e.x
            self._y0 = e.y
            self._ox0, self._oy0 = self._offset
            self._state = ST_CHANGE_OFFSET

    def _on_tk_ButtonRelease_2(self, e):
        if self._state is ST_CHANGE_OFFSET:
            self._state = ST_NORMAL
            del self._x0
            del self._y0
            del self._ox0
            del self._oy0

    def _on_tk_Motion(self, e):
        if self._state is ST_CHANGE_OFFSET:
            d = min(self.winfo_width(), self.winfo_height())
            if not d:
                return
            dx = 2 * (e.x - self._x0) / d
            dy = 2 * (self._y0 - e.y) / d
            self.set_offset(offset = (self._ox0 + dx, self._oy0 + dy))

    def _on_tk_Configure(self, e):
        w = e.width
        h = e.height
        if not (w and h):
            return
        if w > h:
            s = w / h
            self._P = ortho4x4(-s, 1, s, -1)
        else:
            s = h / w
            self._P = ortho4x4(-1, s, 1, -s)

    def set_block(self, block):
        w = block.width
        h = block.height
        if w > h:
            s = 1.5 / w
            self.set_scale(s)
            self.set_offset((-0.75, -0.75 + (w - h) * s * 0.5))
        else:
            s = 1.5 / h
            self.set_scale(s)
            self.set_offset((-0.75 + (h - w) * s * 0.5, -0.75))
        self._bv = BlockView(block)

    def set_scale(self, scale):
        self._scale = scale
        self.invalidate()

    def set_offset(self, offset):
        self._offset = offset
        self.invalidate()

    def __draw__(self):
        glClear(GL_COLOR_BUFFER_BIT)
        glColor3f(1., 1., 1.)
        p.use(
            offset = self._offset,
            scale = self._scale,
            P = self._P,
        )
        for a in self._bv.iter_gl_arrays():
            a()
        self.swapbuffers()


def main():
    root = Tk()
    root.title("Blocks")

    b = Block(aabb = (0, 20, 10, 0))
    b_0 = Block(aabb = (0, 50, 20, 20))
    b_1 = Block(aabb = (20, 30, 40, 0))
    b.add_child(b_0)
    b.add_child(b_1)
    b_0_0 = Block(aabb = (0, 100, 50, 0))
    b_0.add_child(b_0_0)
    b_1_0 = Block(aabb = (0, 15, 20, 0))
    b_1_0.add_child(deepcopy(b))
    b_1.add_child(b_1_0)

    wb = WBlocks(root, block = b)
    wb.pack(expand = True, fill = BOTH)

    root.mainloop()

    return 0


if __name__ == "__main__":
    exit(main() or 0)
