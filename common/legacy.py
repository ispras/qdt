__all__ = [
    "deprecated"
]

""" do not import `stderr` from `sys` right now because it can be swapped at
runtime """

from traceback import (
    extract_stack,
    format_list
)
import sys

def deprecated(message):
    sys.stderr.write(message + "\n")
    # do not print this function and its caller
    for e in format_list(extract_stack()[:-2]):
        sys.stderr.write(e)
