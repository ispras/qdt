__all__ = [
    "deprecated"
]

""" do not import `stderr` from `sys` right now because it can be swapped at
runtime """

import sys
from traceback import \
    extract_stack, \
    format_list

def deprecated(message):
    sys.stderr.write(message + "\n")
    # do not print this function and its caller
    for e in format_list(extract_stack()[:-2]):
        sys.stderr.write(e)
