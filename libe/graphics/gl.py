__all__ = [
    "create_shader",
    "create_gls_program",
    "GLArrays",
    "gl_ready",
    "GLSLProgram",
    "identity4x4",
]


from common import (
    flatten,
    notifier,
)

from ctypes import (
    c_float,
    c_uint16,
    c_void_p,
    sizeof,
)
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    glAttachShader,
    glBindBuffer,
    glBufferData,
    GL_COLOR_ARRAY,
    glColorPointer,
    glCompileShader,
    GL_COMPILE_STATUS,
    glCreateProgram,
    glCreateShader,
    glDisableClientState,
    glDrawElements,
    GL_DYNAMIC_DRAW,
    GL_ELEMENT_ARRAY_BUFFER,
    glEnableClientState,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    glGenBuffers,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    GL_INFO_LOG_LENGTH,
    glLinkProgram,
    GL_LINK_STATUS,
    GL_NORMAL_ARRAY,
    glNormalPointer,
    glShaderSource,
    GL_TEXTURE_COORD_ARRAY,
    glTexCoordPointer,
    GL_TRIANGLES,
    GL_UNSIGNED_SHORT,
    glUseProgram,
    GL_VERTEX_ARRAY,
    glVertexPointer,
    GL_VERTEX_SHADER,
)



identity4x4 = (c_float * 16)(
    1., 0., 0., 0.,
    0., 1., 0., 0.,
    0., 0., 1., 0.,
    0., 0., 0., 1. # no more items!
)


@notifier(
    "ready",
)
class OpenGLContext(object):

    def __init__(self):
        self._ready = False

    @property
    def ready(self):
        return self._ready

    @ready.setter
    def ready(self, ready):
        ready = bool(ready)
        if self._ready is ready:
            return

        if not ready:
            raise NotImplementedError

        self._ready = ready

        self.__notify_ready()

    def watch_all(self, obj):
        super(OpenGLContext, self).watch_all(obj)

_ctx = OpenGLContext()


def gl_ready():
    """ May instantiate those classes any time, but call this when OpenGL is
actually ready.
    """
    _ctx.ready = True


def create_shader(code, kind):
    s = glCreateShader(kind)
    glShaderSource(s, code)
    glCompileShader(s)

    if not glGetShaderiv(s, GL_COMPILE_STATUS):
        info_log_length = glGetShaderiv(s, GL_INFO_LOG_LENGTH)
        if info_log_length > 0:
            raw_log = glGetShaderInfoLog(s)
            raise ValueError(raw_log.decode("unicode_escape"))
        raise ValueError

    return s


def create_gls_program(v, f):
    p = glCreateProgram()

    glAttachShader(p, v)
    glAttachShader(p, f)
    glLinkProgram(p)

    if not glGetProgramiv(p, GL_LINK_STATUS):
        info_log_length = glGetProgramiv(p, GL_INFO_LOG_LENGTH)
        if info_log_length > 0:
            raw_log = glGetProgramInfoLog(p)
            raise ValueError(raw_log.decode("unicode_escape"))
        raise ValueError

    return p


class GLSLProgram(object):

    def __init__(self, vertex_code, fragment_code):
        self._vertex_code = vertex_code
        self._fragment_code = fragment_code

        _ctx.watch_all(self)
        if _ctx.ready:
            self._on_ready()

    def use(self):
        glUseProgram(self._p)

    def _on_ready(self):
        self._vertex = v = create_shader(self._vertex_code, GL_VERTEX_SHADER)
        f = create_shader(self._fragment_code, GL_FRAGMENT_SHADER)
        self._fragment = f
        self._p = create_gls_program(v, f)


client_states = (
    GL_VERTEX_ARRAY,
    GL_COLOR_ARRAY,
    GL_TEXTURE_COORD_ARRAY,
    GL_NORMAL_ARRAY,
)

sizeof_c_float = sizeof(c_float)


class GLArrays(object):

    def __init__(self,
        vertices = None,
        colors = None,
        normals = None,
        texcoords = None,
        indices = None,
        what = GL_TRIANGLES,
    ):
        sources = []
        enables = set()
        pointer_setters = []
        if vertices is not None:
            sources.append(vertices)
            enables.add(GL_VERTEX_ARRAY)
            pointer_setters.append(glVertexPointer)
        if colors is not None:
            sources.append(colors)
            enables.add(GL_COLOR_ARRAY)
            pointer_setters.append(glColorPointer)
        if normals is not None:
            sources.append(normals)
            enables.add(GL_TEXTURE_COORD_ARRAY)
            pointer_setters.append(glNormalPointer)
        if texcoords is not None:
            sources.append(texcoords)
            enables.add(GL_NORMAL_ARRAY)
            pointer_setters.append(glTexCoordPointer)

        # `min` below will raise an exception
        # if not len(sources):
        #     raise ValueError("at least one source array must be geven")

        n = min(map(len, sources))

        stride = 0
        pointers = []
        lengths = []
        for source in sources:
            source_len = len(source[0])
            lengths.append(source_len)
            pointers.append(c_void_p(stride) if stride else None)
            stride += sizeof_c_float * source_len

        if indices is None:
            indices = list(range(0, n))

        mixed = list(flatten(zip(*sources)))
        array = (c_float * len(mixed))(*mixed)
        element_array = (c_uint16 * len(indices))(*indices)

        self._array = array
        self._element_array = element_array
        self._pointer_setters = pointer_setters
        self._pointers = pointers
        self._lengths = lengths
        self._stride = stride
        self._what = what
        self._enables = enables
        self._disables = set(client_states) - enables
        self._n = n

        _ctx.watch_all(self)
        if _ctx.ready:
            self._on_ready()

    def _on_ready(self):
        vao, eao = glGenBuffers(2)

        glBindBuffer(GL_ARRAY_BUFFER, vao)
        glBufferData(GL_ARRAY_BUFFER, self._array, GL_DYNAMIC_DRAW)

        stride =  self._stride
        for setter, ptr, source_len in zip(
            self._pointer_setters,
            self._pointers,
            self._lengths,
        ):
            setter(source_len, GL_FLOAT, stride, ptr)

        glBindBuffer(GL_ARRAY_BUFFER, 0)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, eao)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self._element_array,
            GL_DYNAMIC_DRAW
        )
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

        self._vao = vao
        self._eao = eao

    def draw(self):
        glDrawElements(self._what, self._n, GL_UNSIGNED_SHORT, None)

    def __enter__(self):
        for s in self._enables:
            glEnableClientState(s)
        for s in self._disables:
            glDisableClientState(s)

        glBindBuffer(GL_ARRAY_BUFFER, self._vao)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self._eao)

        return self

    def __exit__(self, *__):
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

    def __call__(self):
        with self as o:
            o.draw()
