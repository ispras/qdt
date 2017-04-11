from common import \
    get_class_total_args

class QOMDescription(object):
    def __init__(self):
        self.project = None

    def __children__(self):
        return []

    def gen_type(self):
        raise Exception("Attempt to create type model from interface type " \
                        + str(self.__class__) + ".")

    def remove_from_project(self):
        self.project.remove_description(self)

"""
DescriptionOf decorator is used to extend a class to one that could be used
as description of QOM type template. Main purpose is to simplify definition
of QOM type template description classes.
"""
def DescriptionOf(QOMTemplate):
    """ Get arguments of QOM type template initializer and save them in
    defaults of function 'decorate'."""
    pa, kwa = get_class_total_args(QOMTemplate)

    def decorate(klass, pa = pa, kwa = kwa):
        # default method to generate QOM type from description
        def gen_type(self, __class = QOMTemplate, __pa = pa, __kwa = kwa):
            kwa = {}
            for key in __kwa:
                val = getattr(self, key)
                kwa[key] = val

            return __class(*[ getattr(self, arg) for arg in __pa ], **kwa)

        # default method to save description to Python script
        def __gen_code__(self, gen, __pa = pa, __kwa = list(kwa.keys())):
            gen.reset_gen(self)

            for attr in __pa + __kwa:
                val = getattr(self, attr)
                gen.gen_field("%s = %s" % (attr, gen.gen_const(val)))

            if self.compat:
                for attr, val in self.compat.items():
                    gen.gen_field(attr + " = ")
                    gen.pprint(val)

            gen.gen_end()

        # Common __init__ method for all descriptions.
        # Positional arguments are simply copied.
        assignments = [ "self.{arg} = {arg}".format(arg = arg) for arg in pa ]

        # Special handling of default values of keyword arguments is required
        kwargs = []
        for arg, default in kwa.items():
            if isinstance(default, (list, dict, set)):
                # containers in defaults must be copied
                val = "%s(%s)" % (type(default).__name__, arg)
            else:
                val = arg
            kwargs.append("%s = %s" % (arg, repr(default)))
            assignments.append("self.%s = %s" % (arg, val))

        # Template for __init__
        init_code = """
def __init__(self, {pa}, {kwa}, **compat):
    QOMDescription.__init__(self)
    self.compat = compat
    {assignments}{description_init}
"""

        init_code = init_code.format(
            pa = ", ".join(pa),
            kwa = ", ".join(kwargs),
            assignments = "\n    ".join(assignments),
            # Description class may provide __description_init__ method
            # that performs some extra post-initialization.
            description_init = "\n\n    self.__description_init__()" \
                if "__description_init__" in klass.__dict__ else ""
        )

        # __init__ method will be searched in locals
        _locals = {}
        # Only one global name is required to define __init__: QOMDescription
        exec(init_code, { "QOMDescription" : QOMDescription }, _locals)

        # Override initializer.
        klass.__init__ = _locals["__init__"]

        # Do not override gen_type and __gen_code__ if provided
        if "gen_type" not in klass.__dict__:
            klass.gen_type = gen_type
        if "__gen_code__" not in klass.__dict__:
            klass.__gen_code__ = __gen_code__

        return klass

    return decorate
