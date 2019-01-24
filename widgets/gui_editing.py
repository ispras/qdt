__all__ = [
    "GUIProjectOperation"
      , "GUIPOp_SetBuildPath"
      , "GUIDescriptionOperation"
          , "POp_SetDescLayout"
]

from qemu import (
    ProjectOperation
)
from copy import (
    deepcopy
)
from common import (
    mlget as _
)
from .gui_project import (
    GUIProject
)


def _check_context(project):
    if not isinstance(project, GUIProject):
        raise ValueError("The 'project' argument is not a GUI project.")

""" The difference is the project should be a _GUI_ project. """
class GUIProjectOperation(ProjectOperation):

    def __backup__(self, project):
        _check_context(project)
        super(GUIProjectOperation, self).__backup__(project)

    def __do__(self, project):
        _check_context(project)
        super(GUIProjectOperation, self).__do__(project)

    def __undo__(self, project):
        _check_context(project)
        super(GUIProjectOperation, self).__undo__(project)

    def __description__(self, project):
        _check_context(project)
        return super(GUIProjectOperation, self).__description__(project)


class GUIPOp_SetBuildPath(GUIProjectOperation):
    def __init__(self, path, *args, **kw):
        GUIProjectOperation.__init__(self, *args, **kw)
        self.new_path = None if path is None else deepcopy(path)

    def _backup(self):
        self.old_path = \
            None if self.p.build_path is None else deepcopy(self.p.build_path)

    def _do(self):
        self.p.build_path = \
            None if self.new_path is None else deepcopy(self.new_path)

    def _undo(self):
        self.p.build_path = \
            None if self.old_path is None else deepcopy(self.old_path)

    def __write_set__(self):
        return GUIProjectOperation.__write_set__(self) + [
            "build_path"
        ]

    def _description(self):
        if self.new_path is None:
            return _("Forget project build path value '%s'") % self.old_path
        elif self.old_path is None:
            return _("Specify project build path value '%s'") % self.new_path
        else:
            return _("Change project build path value '%s' to '%s'") % (
                self.old_path, self.new_path
            )

class GUIDescriptionOperation(GUIProjectOperation):
    def __init__(self, description, *args, **kw):
        GUIProjectOperation.__init__(self, *args, **kw)

        self.desc_name = str(description.name)

    def find_desc(self):
        return next(self.p.find(name = self.desc_name))

class POp_SetDescLayout(GUIDescriptionOperation):
    def __init__(self, new_layout, *args, **kw):
        GUIDescriptionOperation.__init__(self, *args, **kw)

        if new_layout is not None:
            self.new_layout = deepcopy(new_layout)
        else:
            self.new_layout = None

    def _backup(self):
        layouts = self.p.get_layout_objects(self.desc_name)

        if layouts:
            self.prev_layouts = deepcopy(layouts)
        else:
            self.prev_layouts = None

    def _do(self):
        if self.prev_layouts is not None:
            self.p.delete_layouts(self.desc_name)
        if self.new_layout is not None:
            self.p.add_layout_object(deepcopy(self.new_layout))

    def _undo(self):
        if self.new_layout is not None:
            self.p.delete_layouts(self.desc_name)
        if self.prev_layouts is not None:
            self.p.add_layout_objects(deepcopy(self.prev_layouts))

    def _description(self):
        if self.prev_layouts is None:
            return _("Set layout for '%s' description representation.") % \
                self.desc_name
        elif self.new_layout is None:
            return _("Remove layouts of '%s' description representation.") % \
                self.desc_name
        else:
            return _("Replace layout of '%s' description representation.") % \
                self.desc_name
