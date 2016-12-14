class QOMDescription(object):
    def __init__(self, name, directory):
        self.name = name
        self.directory = directory
        self.project = None

    def __children__(self):
        return []

    def gen_type(self):
        raise Exception("Attempt to create type model from interface type " \
                        + str(self.__class__) + ".")

    def remove_from_project(self):
        self.project.remove_description(self)
