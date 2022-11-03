__all__ = [
    "preprocess"
]


def preprocess(o):
    """\
Preprocessing is used to save user defined objects as they were created by
the user.
User defined objects could be changed during operation because of various
reasons...
    - Automatic arguments values guessing, based on provided argument values.
    - Compatibility. Adjusting old projects to new version of the tool.
    - ...
Making those changed in place may result in...
    - Growing of the project script after saving.
    - ...
Objects those automatically changes self must define a `__preprocess__`
callable attribute which should return a copy of self (or compatible object)
which the object is allowed to change as it wish.
    """
# TODO: There already is a much more complicated mechanism that targets the
#       same problem. See qemu/qom_desc.py. This one is more generic and
#       should be used whatever is possible. Even replacing first one.
    try:
        pp = o.__preprocess__
    except AttributeError:
        return o
    else:
        return pp()
