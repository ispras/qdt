# Find out which of system python is backing gdb.
# Then: sudo [python] -m pip install pydevd
# import sys
# print(sys.path)

# A PyDev Debug Server must be active.
# E.g.: Launch Eclipse with PyDev installed, then Pydev -> Start Debug Server
# and open "Debug" perspective.
import pydevd

# Execution of this script is paused after this command with corresponding
# PyDev GUI reaction.
pydevd.settrace()

class MyBr(gdb.Breakpoint):

    def stop(self):
        i = gdb.parse_and_eval("i")
        # You may set a breakpoint at this line (in Eclipse PyDev editor).
        return i > 5

MyBr("main.c:5")
