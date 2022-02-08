__all__ = [
    "feed_var_to_attr"
]


def feed_var_to_attr(var, obj, attr):
    """
Creates a feedback from the Tk `var`iable to the `attr`ibute of the `obj`ect.
    """

    def w(*__):
        setattr(obj, attr, var.get())

    var.trace_variable("w", w)
