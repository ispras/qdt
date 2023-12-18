__all__ = [
    "create_shader",
    "create_gls_program",
]


from OpenGL.GL import (
    glAttachShader,
    glCompileShader,
    GL_COMPILE_STATUS,
    glCreateProgram,
    glCreateShader,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    GL_INFO_LOG_LENGTH,
    glLinkProgram,
    GL_LINK_STATUS,
    glShaderSource,
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
