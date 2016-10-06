from common import \
    InverseOperation

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

class DescriptionOperation(ProjectOperation):
    def __init__(self, description, *args, **kw):
        ProjectOperation.__init__(self, *args, **kw)
        # desc is cached value, the description identifier is desc_name
        self.desc = description
        self.desc_name = str(self.desc.name)

