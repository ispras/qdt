from inspect import \
    getargspec

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
