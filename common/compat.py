
"""
The module defines set of compatibility items which are not implemented in Six.
"""

from six import \
    PY3, \
    PY2

if PY3:
    def execfile(filename, globals = None, locals = None):
        f = open(filename, "rb")
        content = f.read()
        f.close()
        obj = compile(content, filename, "exec")
        exec(content, globals, locals)

    pass
elif PY2:
    execfile = execfile
    pass
else:
    raise Exception("Unknown Python version.")
