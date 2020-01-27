__all__ = [
    "notifier"
]

from inspect import (
    getargspec
)
from .os_wrappers import (
    ee
)


def gen_init_wrapper(wrapped_init, cb_list_name):
    """ Creates a wrapper for initializer `__init__` (given by `wrapped_init`)
that adds callback list to each instance. Also preserves argument specification
and doc string of `wrapped_init`. It makes `notifier` decorator more
transparent.
    """
    code = "def __init__("

    try:
        args, varargs, keywords, defaults = getargspec(wrapped_init)
    except TypeError:
        # XXX: Is there a technique to get argspec for a builtin function?
        # Because of `notifier` is a class decorator, `wrapped_init` must have
        # `self` argument. But amount of rest arguments is unpredictable.
        # But varargs are used for flexibility.
        args, varargs, keywords, defaults = ["self"], "a", "kw", []

    if defaults:
        arg_strs = list(args[:-len(defaults)]) + list(
            (a + " = " + repr(v)) for a, v in zip(
                args[-len(defaults):], defaults
            )
        )
        arg_to_init = list(args[:-len(defaults)]) + list(
            (a + " = " + a) for a in args[-len(defaults):]
        )
    else:
        arg_strs = args
        arg_to_init = list(args)

    if varargs:
        arg_strs.append("*" + varargs)
        arg_to_init.append("*" + varargs)

    if keywords:
        arg_strs.append("**" + keywords)
        arg_to_init.append("**" + keywords)

    code += ", ".join(arg_strs) + "):\n"

    if wrapped_init.__doc__:
        code += "    '''%s'''\n" % wrapped_init.__doc__.replace("'", '\'')
    # Define callback list before calling of original __init__ to allow
    # it assign watchers.
    code += "    setattr(self, '" + cb_list_name + "', [])\n"
    code += "    wrapped_init(" + ", ".join(arg_to_init) + ")\n"

    if ee("QDT_DEBUG_NOTIFIER"):
        print(code)

    _globals = {"wrapped_init" : wrapped_init}

    exec(code, _globals)

    return _globals["__init__"]

# "Function factory" approach is used to meet "late binding" problem.
# http://stackoverflow.com/questions/3431676/creating-functions-in-a-loop/

def gen_event_helpers(klass, event):
    # Callback list is private.
    cb_list_name = "_" + klass.__name__ + "__" + event

    init_wrapper = gen_init_wrapper(klass.__init__, cb_list_name)

    def add_callback(self, callback):
        getattr(self, cb_list_name).append(callback)

    def remove_callback(self, callback):
        getattr(self, cb_list_name).remove(callback)

    def notify(self, *args, **kw):
        callbacks = getattr(self, cb_list_name)
        # Because a listener (callback) can add and/or remove
        # listeners during operation, the listener list must be
        # copied before the process.
        for callback in list(callbacks):
            # Callback denial does not take effect during current notification.
            callback(*args, **kw)

    return init_wrapper, add_callback, remove_callback, notify

def notifier(*events):
    def add_events(klass, events = events):
        for event in events:
            __init_wrapper__, add_callback, remove_callback, __notify = \
                gen_event_helpers(klass, event
            )

            klass.__init__ = __init_wrapper__
            setattr(klass, "watch_" + event, add_callback)
            setattr(klass, "unwatch_" + event, remove_callback)

            # Notification method is private.

            # About private methods:
            # http://stackoverflow.com/questions/9990454
            # https://docs.python.org/3/reference/expressions.html#atom-identifiers

            # XXX: is there a recommended method to define class private
            # methods externally?
            notify_name = "_" + klass.__name__ + "__notify_" + event
            setattr(klass, notify_name, __notify)

        def watch(self, event_name, cb):
            getattr(self, "watch_" + event_name)(cb)

        def unwatch(self, event_name, cb):
            getattr(self, "unwatch_" + event_name)(cb)

        klass.watch = watch
        klass.unwatch = unwatch

        if not hasattr(klass, "_events"):
            klass._events = tuple(events)
        else:
            klass._events += tuple(events)

        return klass

    return add_events
