from common import \
    gen_class_args, \
    get_class_defaults, \
    InverseOperation

from importlib import \
    import_module

class ProjectOperation(InverseOperation):
    def __init__(self, project, *args, **kw):
        InverseOperation.__init__(self, *args, **kw)

        self.p = project

    """
    The InverseOperation defines no read or write sets. Instead it raises an
    exception. As this is a base class of all machine editing operations it
    should define the sets. The content of the sets is to be defined by
    subclasses.
    """

    def __write_set__(self):
        return []

    def __read_set__(self):
        return []

class QemuObjectCreationHelper(object):
    """ The class helps implement Qemu model object creation operations. It
    automates handling of arguments for __init__ method of created objects.
    The helper class __init__ method gets lists of handled class __init__
    arguments. Then it moves them from kw dictionary to self. They are stored
    as attributes of the helper class instance. Names of the attributes are
    built using user defined prefix and names of corresponding handled class
    __init__ arguments. The 'new' method of the helper class creates object of
    handled class with this arguments.
    """

    def __init__(self, class_name, kw, arg_name_prefix = ""):
        self.nc = class_name

        if arg_name_prefix and arg_name_prefix[0] == '_':
            """
            If attribute is set like o.__my_attr. The getattr(o, "__my_attr")
will return AttributeError while the attribute is accessible by o.__my_attr
expression. The valid attribute name for getattr is something about
_MyClassName__my_attr in this case. It is Python internals...
            """
            raise Exception( """Prefix for target constructor arguments storing\
 should not start with '_'."""
            )

        self.prefix = arg_name_prefix

        for n in self.al + self.kwl:
            if n in kw:
                setattr(self, self.prefix + n, kw.pop(n))

    @property
    def nc(self):
        return self._nc[5:]

    @nc.setter
    def nc(self, class_name):
        if class_name:
            self._nc = "qemu." + class_name
            self.al, self.kwl = gen_class_args(self._nc)
        else:
            self._nc = "qemu."
            self.al, self.kwl = [], []

    def new(self):
        segments = self._nc.split(".")
        module, class_name = ".".join(segments[:-1]), segments[-1]
        Class = getattr(import_module(module), class_name)

        args = []
        for n in self.al:
            try:
                val = getattr(self, self.prefix + n)
            except AttributeError:
                val = None
            args.append(val)

        kw = {}
        for n in self.kwl:
            try:
                val = getattr(self, self.prefix + n)
            except AttributeError:
                pass
            else:
                kw[n] = val

        return Class(*args, **kw)

    """ The method imports from origin values for arguments of current class
__init__ method. By default the method uses getattr method. The attrinutes names
are assumed to be same as names of __init__ arguments. It is incorrect the
the origin object class can provide __get_init_arg_val__ method. The method
should be getattr-like:
    1-st argument is the reference to the origin
    2-nd argument is name of __init__ argument the value for which should be
returned.

Basic example:

    def __get_init_arg_val__(self, arg_name):
        return getattr(self, arg_name)

The behaviour in this case is same as if no __get_init_arg_val__ method is
defined.

    The import_argument_values do not imports complicated values. Supported
types are:
    bool
    int
    long
    str
    unicode
None values are imported too.

    """
    def import_argument_values(self, origin):
        try:
            import_method = type(origin).__get_init_arg_val__
        except AttributeError:
            import_method = getattr

        for attr_name in self.al:
            try:
                val = import_method(origin, attr_name)
            except AttributeError:
                raise Exception(
                    "Cannot import value of argument with name '%s'" % attr_name
                )

            # import values of basic types only
            t = type(val)
            if not (
                    val is None
                or  t is bool
                or  t is int
                or  t is long
                or  t is str
                or  t is unicode
            ):
                # print "skipping %s of type %s" % (attr_name, t.__name__)
                continue

            setattr(self, self.prefix + attr_name, val)

        def_args = get_class_defaults(self._nc)

        for attr_name in self.kwl:
            try:
                val = import_method(origin, attr_name)
            except AttributeError:
                # values of arguments with defaults are not important enough.
                continue

            # import values of basic types only
            t = type(val)
            if not (
                    val is None
                or  t is bool
                or  t is int
                or  t is long
                or  t is str
                or  t is unicode
            ):
                # print "skipping %s of type %s" % (attr_name, t.__name__)
                continue

            # do not store default values
            if def_args[attr_name] == val:
                continue

            setattr(self, self.prefix + attr_name, val)

    def set_with_origin(self, origin):
        self.nc = type(origin).__name__

        self.import_argument_values(origin)

class POp_AddDesc(ProjectOperation, QemuObjectCreationHelper):
    def __init__(self, desc_class_name, desc_name, *args, **kw):
        if not "directory" in kw:
            kw["directory"] = "hw"
        kw["name"] = desc_name

        QemuObjectCreationHelper.__init__(self, desc_class_name, kw, "desc_")
        ProjectOperation.__init__(self, *args, **kw)

        self.name = desc_name

    def __backup__(self):
        pass

    def __do__(self):
        self.p.add_description(self.new())

    def __undo__(self):
        desc = self.p.find(name = self.name).next()

        """ It is unexpected way to type independently check for the description
        is empty. """
        if desc.__children__():
            raise Exception("Not empty description removing attempt.")

        self.p.remove_description(desc)

    def __write_set__(self):
        return ProjectOperation.__write_set__(self) + [
            str(self.name)
        ]

class DescriptionOperation(ProjectOperation):
    def __init__(self, description, *args, **kw):
        ProjectOperation.__init__(self, *args, **kw)

        self.desc_name = str(description.name)

    def find_desc(self):
        return self.p.find(name = self.desc_name).next()
