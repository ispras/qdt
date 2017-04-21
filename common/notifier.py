__all__ = [
    "Notifier"
]

def Notifier(*events):
    def add_events(klass, events = events):
        for event in events:
            cb_list_name = "_" + klass.__name__ + "__" + event

            # Wrapper for constructor that adds callback list to each instance
            """ XXX: Assume that neither constructor nor any event hander have
            keyword argument with name __wrapped_init__ or __cb_list_name. Then
            apply a dark magic. """
            def __init_wrapper__(self, *args,
                __wrapped_init__ = klass.__init__,
                __cb_list_name = cb_list_name, **kw
            ):
                __wrapped_init__(self, *args, **kw)
                setattr(self, __cb_list_name, list())

            klass.__init__ = __init_wrapper__
            # Define utility functions for current event
            def add_callback(self, callback, __cb_list_name = cb_list_name):
                getattr(self, __cb_list_name).append(callback)

            def remove_callback(self, callback, __cb_list_name = cb_list_name):
                getattr(self, __cb_list_name).remove(callback)

            def __notify(self, *args, __cb_list_name = cb_list_name, **kw):
                callbacks = getattr(self, __cb_list_name)
                """ Because listeners could add and/or remove callbacks during
                notification, the listener list should be copied before
                the process. """
                for callback in list(callbacks):
                    # Callback denial does not take effect during current
                    # notification.
                    callback(*args, **kw)

            setattr(klass, "watch_" + event, add_callback)
            setattr(klass, "unwatch_" + event, remove_callback)

            """ Notification method must be private.

About private methods:
http://stackoverflow.com/questions/9990454
https://docs.python.org/3/reference/expressions.html#atom-identifiers
            """

            """ XXX: is there a recommended method to define class private
            methods externally? While external definition of class private
            methods is not recommended. """
            notify_name = "_" + klass.__name__ + "__notify_" + event
            setattr(klass, notify_name, __notify)

        return klass

    return add_events
