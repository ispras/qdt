
"""
The module defines set of compatibility items which are not implemented in Six.
"""

from six import \
    PY3, \
    PY2

if PY3:
    pass
elif PY2:
    pass
else:
    raise Exception("Unknown Python version.")
