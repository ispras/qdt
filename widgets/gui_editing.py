from qemu import \
    ProjectOperation

from copy import \
    deepcopy

from gui_project import \
    GUIProject

""" The difference is the project should be a _GUI_ project. """
class GUIProjectOperation(ProjectOperation):
    def __init__(self, project, *args, **kw):
        if not isinstance(project, GUIProject):
            raise Exception("The 'project' argument is not a GUI project.")

        ProjectOperation.__init__(self, project, *args, **kw)

class GUIDescriptionOperation(GUIProjectOperation):
    def __init__(self, description, *args, **kw):
        GUIProjectOperation.__init__(self, *args, **kw)

        self.desc_name = str(description.name)

    def find_desc(self):
        return self.p.find(name = self.desc_name).next()

class POp_SetDescLayout(GUIDescriptionOperation):
    def __init__(self, new_layout, *args, **kw):
        GUIDescriptionOperation.__init__(self, *args, **kw)

        if new_layout is not None:
            self.new_layout = deepcopy(new_layout)
        else:
            self.new_layout = None

    def __backup__(self):
        layouts = self.p.get_layouts(self.desc_name)

        if layouts:
            self.prev_layouts = deepcopy(layouts)
        else:
            self.prev_layouts = None

    def __do__(self):
        if self.new_layout is not None:
            self.p.set_layout(self.desc_name, deepcopy(self.new_layout))
        else:
            self.p.delete_layouts(self.desc_name)

    def __undo__(self):
        if self.prev_layouts is not None:
            self.p.set_layouts(self.desc_name, deepcopy(self.prev_layouts))
        else:
            self.p.delete_layouts(self.desc_name)
