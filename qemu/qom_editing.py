from project_editing import \
    DescriptionOperation

from copy import \
    deepcopy as dcp

from common import \
    mlget as _

class DOp_SetAttr(DescriptionOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        DescriptionOperation.__init__(self, *args, **kw)

        self.attr = str(attribute_name)
        self.val = dcp(new_value)

    def __read_set__(self):
        return DescriptionOperation.__read_set__(self) + [
            str(self.desc_name)
        ]

    def __write_set__(self):
        return DescriptionOperation.__write_set__(self) + [
            (str(self.desc_name), str(self.attr))
        ]

    def __backup__(self):
        self.old_val = dcp(getattr(self.find_desc(), self.attr))

    def __do__(self):
        setattr(self.find_desc(), self.attr, dcp(self.val))

    def __undo__(self):
        setattr(self.find_desc(), self.attr, dcp(self.old_val))

    def __description__(self):
        return _("Set '%s' of '%s' to '%s'.") % (
            self.attr,
            self.desc_name,
            str(self.val)
        )

class SetDescriptionReferenceAttribute(DescriptionOperation):
    def __init__(self, attribute_name, new_value, *args, **kw):
        DescriptionOperation.__init__(self, *args, **kw)

        self.attr = str(attribute_name)
        self.val = new_value

    def __read_set__(self):
        # Note that new referenced value is probably to be in read set.
        return DescriptionOperation.__read_set__(self) + [
            str(self.desc_name)
        ]

    def __write_set__(self):
        return DescriptionOperation.__write_set__(self) + [
            (str(self.desc_name), str(self.attr))
        ]

    def __backup__(self):
        self.old_val = getattr(self.find_desc(), self.attr)

    def __do__(self):
        setattr(self.find_desc(), self.attr, self.val)

    def __undo__(self):
        setattr(self.find_desc(), self.attr, self.old_val)
