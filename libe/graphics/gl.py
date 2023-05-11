__all__ = [
    "create_shader",
    "create_gls_program",
    "GLArrays",
    "gl_ready",
    "GLSLProgram",
    "identity4x4",
    "ortho4x4",
]


from common import (
    flatten,
    notifier,
)
from ..grammars.glsl.v1_50 import (
    parser as glsl_1_50_parser,
)

from ctypes import (
    c_float,
    c_uint16,
    c_void_p,
    sizeof,
)
from itertools import (
    chain,
)
from lark import (
    Token,
    Transformer,
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
    glGetUniformLocation,
    GL_INFO_LOG_LENGTH,
    glLinkProgram,
    GL_LINK_STATUS,
    GL_NORMAL_ARRAY,
    glNormalPointer,
    glShaderSource,
    GL_TEXTURE_COORD_ARRAY,
    glTexCoordPointer,
    GL_TRIANGLES,
    glUniform1f,
    glUniform1i,
    glUniform2fv,
    glUniform3fv,
    glUniform4fv,
    glUniformMatrix4fv,
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


def ortho4x4(l, t, r, b, f = -1., n = 1.):
    w = r - l
    h = t - b
    d = f - n
    return (c_float * 16)(
              2. / w,           0.,           0., 0.,
                  0.,       2. / h,           0., 0.,
                  0.,           0.,      -2. / d, 0.,
        -(r + l) / w, -(t + b) / h, -(f + n) / d, 1. # no more items!
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


# shader source code analysis
class GLSLTypeQualifier:
    pass

UNIFORM = GLSLTypeQualifier()

class GLSLTypeQualifiers(set):
    pass

class GLSLType(object):

    def __init__(self):
        self.qualifiers = GLSLTypeQualifiers()

class GLSLVariable(object):

    def __init__(self, glsl_type, name, initializer = None):
        self.type = glsl_type
        self.name = str(name)
        self.initializer = initializer

group = lambda iters: list(i for i in chain(*iters) if i is not None)

class GLSLProgAnalyzer(Transformer):

    def translation_unit(self, s):
        return group(s)

    def function_definition(self, s):
        # not required
        return [None]

    def toplevel_declarations(self, s):
        return group(s)

    def declarations(self, s):
        if isinstance(s, GLSLTypeQualifiers):
            return None
        if isinstance(s, list):
            return s
        else:
            return [s]

    def precision_declaration(self, __):
        # Not a type declaration, but a compiller hint.
        # E.g.: precision mediump float;
        return None

    def scalar_declaration(self, s):
        return GLSLVariable(*s)

    def fully_specified_type(self, s):
        if len(s) == 1:
            t = s[0]
        else:
            t = s[1]
            t.qualifiers |= s[0]
        return t

    def type_qualifiers(self, s):
        return GLSLTypeQualifiers(s)

    def uniform(self, __):
        return UNIFORM

    def type_specifier_nonarray(self, s):
        s = s[0]
        t = GLSLType()
        if isinstance(s, Token):
            # CNAME or "void"
            t.name = str(s)
        else:
            # struct_specifier, not implemented yet
            t.name = "[struct]"
        return t

    def type_specifier_prec(self, s):
        # precision_qualifier is not implemented yet
        __, t = s
        return t

    def type_specifier_array(self, s):
        # arrays not implemented yet
        t = s[0]
        return t

    def type_specifier(self, s):
        return s[0]


# uniforms loading helpers
uniform_loaders = dict(
    float = glUniform1f,
    sampler2D = glUniform1i,
    mat4 = lambda uid, buf : glUniformMatrix4fv(uid, 1, False, buf),
    vec2 = lambda uid, buf : glUniform2fv(uid, 1, buf),
    vec3 = lambda uid, buf : glUniform3fv(uid, 1, buf),
    vec4 = lambda uid, buf : glUniform4fv(uid, 1, buf),
)


class GLSLProgram(object):

    def __init__(self, vertex_code, fragment_code):
        uniforms = {}

        for code in (vertex_code, fragment_code):
            an = GLSLProgAnalyzer()
            tree = glsl_1_50_parser.parse(code)
            # print(tree.pretty())
            for i in an.transform(tree):
                if isinstance(i, GLSLVariable):
                    if UNIFORM in i.type.qualifiers:
                        uniforms[i.name] = i.type.name

        self._vertex_code = vertex_code
        self._fragment_code = fragment_code
        self._uniforms = uniforms  # ; print(uniforms)

        _ctx.watch_all(self)
        if _ctx.ready:
            self._on_ready()

    def use(self, **uniforms_assignments):
        glUseProgram(self._p)

        loaders = self._loaders

        for n, v in uniforms_assignments.items():
            loaders[n](v)

    def _on_ready(self):
        self._vertex = v = create_shader(self._vertex_code, GL_VERTEX_SHADER)
        f = create_shader(self._fragment_code, GL_FRAGMENT_SHADER)
        self._fragment = f
        self._p = p = create_gls_program(v, f)

        # auto uniforms handling
        self._loaders = loaders = {}
        for n, t in self._uniforms.items():
            u_loc = glGetUniformLocation(p, n)
            if u_loc < 0:
                print("%s: uniform was dropped by linker" % (n,))
                continue

            try:
                ldr = uniform_loaders[t]
            except KeyError:
                print("%s: uniform type %s loading is not implemented" % (
                    n, t
                ))
                continue

            loaders[n] = lambda val, u_loc = u_loc, ldr = ldr: ldr(u_loc, val)


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
