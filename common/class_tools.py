from importlib import \
    import_module

"""
The function returns lists of positional and key word arguments of
class constructor. 
"""
def gen_class_args(full_class_name):
    segments = full_class_name.split(".")
    module, class_name = ".".join(segments[:-1]), segments[-1]
    Class = getattr(import_module(module), class_name)

    all_vars = Class.__init__.__code__.co_varnames
    # Get all arguments without "self".
    all_args = all_vars[:Class.__init__.__code__.co_argcount][1:]

    """
    The code below distinguishes positional arguments and key word
    arguments. Assume that all key word arguments do have defaults and
    only they do.
    """

    if Class.__init__.__defaults__ is not None:
        kwarg_count = len(Class.__init__.__defaults__)
        al = all_args[:-kwarg_count]
        kwl = all_args[-kwarg_count:]
    else:
        al, kwl = list(all_args), []

    return al, kwl
