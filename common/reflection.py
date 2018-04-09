__all__ = [
    "get_default_args"
  , "get_class_total_args"
]

from inspect import (
    getmro,
    getargspec
)
from collections import (
    OrderedDict
)

# http://stackoverflow.com/questions/12627118/get-a-function-arguments-default-value
def get_default_args(func):
    """
    returns a dictionary of arg_name:default_values for the input function
    """
    args, varargs, keywords, defaults = getargspec(func)
    if defaults is not None:
        return dict(zip(args[-len(defaults):], defaults))
    else:
        return {}

def get_class_total_args(Class):
    # positional arguments
    total_pa = []
    # keyword arguments
    total_kwa = OrderedDict()

    """ Assume that **keywords argument is used to pass keyword arguments
    to parent classes. As soon as *varargs argument is used to pass
    positional arguments. See example in __main__ below.

    Positional arguments must be concatenated skipping same named ones.

    Keyword arguments must be merged into total dictionary. Default values
    of child class must dominate.
    """

    merge_pa = True
    merge_kwa = True

    for Class in getmro(Class):
        args, varargs, keywords, defaults = getargspec(Class.__init__)

        kwargs_count = 0 if defaults is None else  len(defaults)

        # slice from index 1 to exclude 'self'
        if kwargs_count > 0:
            pa = args[1:-kwargs_count]
        else:
            pa = args[1:]

        if merge_pa and pa:
            if total_pa:
                for i, (child_arg, parent_arg) in enumerate(
                    zip(total_pa, pa)
                ):
                    # same named arguments must be skipped
                    if child_arg != parent_arg:
                        break
                else:
                    i += 1
                total_pa.extend(pa[i:])
            else:
                total_pa = pa

        if not varargs:
            merge_pa = False
            if not merge_kwa:
                break

        if merge_kwa and kwargs_count:
            kwa = OrderedDict(zip(args[-kwargs_count:], defaults))

            for key, val in kwa.items():
                if key not in total_kwa:
                    total_kwa[key] = val

        if not keywords:
            merge_kwa = False
            if not merge_pa:
                break

    return total_pa, total_kwa

if __name__ == "__main__":
    class Elder(object):
        def __init__(self, kind, ekw0 = 0xDEAD, ekw1 = 0xBEEF):
            pass

    class Parent(Elder):
        def __init__(self, first_name, last_name, do = "eats", *elder_args,
                **elder_kw
            ):
            super(Parent, self).__init__(*elder_args, **elder_kw)

    class Child(Parent):
        def __init__(self, first_name, who = "beef", do = "becomes",
                *parent_args, **parent_kw
            ):
            super(Child, self).__init__(do = do, *parent_args, **parent_kw)

    """
    Total positional argumetns of Child are:
    [
        "first_name",
        "last_name",
        "kind"
    ]

    Total default values of Child are:
    {
        "who": "beef"
        "do" : "becomes",
        "ekw0" : 0xDEAD,
        "ekw1" : 0xBEEF,
        }
    """

    print(get_class_total_args(Child))

