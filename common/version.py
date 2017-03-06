def parse_version(ver):
    ver_parts = ver.split(".")

    if ver_parts:
        major = int(ver_parts.pop(0))
    else:
        major = 0

    if ver_parts:
        minor = int(ver_parts.pop(0))
    else:
        minor = 0

    if ver_parts:
        micro = int(ver_parts.pop(0))
    else:
        micro = 0

    if ver_parts:
        suffix = ".".join(ver_parts)
    else:
        suffix = ""

    return (major, minor, micro, suffix)

