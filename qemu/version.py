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

class QEMUVersionParameterDescription(object):
    def __init__(self, name, new_value, old_value = None):
        self.name = name
        self.new_value = new_value
        self.old_value = old_value

class QEMUVersionDescription(object):
    def __init__(self, version_string, parameters):
        self.version = parse_version(version_string)
        self.parameters = list(parameters)

    def get_parameter(self, name):
        return self.parameters[name]

    def compare(self, version_string):
        version = parse_version(version_string)

        for i in xrange(0, 3):
            if self.version[i] != version[i]:
                return version[i] - self.version[i]

        if self.version[3] == "" and version[3] == "":
            return 0
        raise Exception("Lexical comparation of version suffix is not implemented yet!")

# Warning! Preserve order!
qemu_versions = [
]

version_parameters = None
version_string = None

def initialize(_version_string):
    parameters = {}

    for qvd in qemu_versions:
        take_new = qvd.compare(_version_string) >= 0

        for pd in qvd.parameters:
            if pd.name in parameters.keys():
                if take_new:
                    parameters[pd.name] = pd.new_value
            else:
                if take_new:
                    parameters[pd.name] = pd.new_value
                elif pd.old_value is None:
                    raise Exception("No old value for parameter '%s' was found." % pd.name)
                else:
                    parameters[pd.name] = pd.old_value

    global version_parameters
    version_parameters = parameters

    global version_string
    version_string = _version_string

def get_vp():
    return version_parameters
