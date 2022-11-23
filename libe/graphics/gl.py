__all__ = [
    "create_shader",
    "create_gls_program",
    "GLSLProgram",
]


from OpenGL.GL import (
    glAttachShader,
    glCompileShader,
    GL_COMPILE_STATUS,
    glCreateProgram,
    glCreateShader,
    GL_FRAGMENT_SHADER,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    GL_INFO_LOG_LENGTH,
    glLinkProgram,
    GL_LINK_STATUS,
    glShaderSource,
    glUseProgram,
    GL_VERTEX_SHADER,
)


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

        self._vertex = v =create_shader(vertex_code, GL_VERTEX_SHADER)
        self._fragment = f = create_shader(fragment_code, GL_FRAGMENT_SHADER)
        self._p = create_gls_program(v, f)

    def use(self):
        glUseProgram(self._p)
