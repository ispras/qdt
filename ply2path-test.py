try:
    from ply import *
except ImportError:
    pass
else:
    print("WARNING: There is a global ply version. Keep it in mind.")

print(",\n    '".join(str(globals()).split(", '")))

from common.ply2path import *

from ply import *

print("After:")
print(",\n    '".join(str(globals()).split(", '")))
