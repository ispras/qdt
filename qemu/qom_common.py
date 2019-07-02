__all__ = [
    "QOMPropertyType"
      , "QOMPropertyTypeLink"
      , "QOMPropertyTypeString"
      , "QOMPropertyTypeBoolean"
      , "QOMPropertyTypeInteger"
  , "QOMPropertyValue"
  , "idon"
]


from common import (
    same
)
from source import (
    Type
)


def idon(node):
    "ID Or None. Given an object returns `id` attr. Given a None returns None."
    if node is None:
        return None
    return node.id

# properties
class QOMPropertyType(object):
    set_f = None
    build_val = None


class QOMPropertyTypeLink(QOMPropertyType):
    set_f = "object_property_set_link"


class QOMPropertyTypeString(QOMPropertyType):
    set_f = "object_property_set_str"


class QOMPropertyTypeBoolean(QOMPropertyType):
    set_f = "object_property_set_bool"


class QOMPropertyTypeInteger(QOMPropertyType):
    set_f = "object_property_set_int"

    @staticmethod
    def build_val(prop_val):
        if Type.exists(prop_val):
            return str(prop_val)
        return "0x%0x" % prop_val


class QOMPropertyValue(object):

    def __init__(self,
        prop_type,
        prop_name,
        prop_val
        ):
        self.prop_type = prop_type
        self.prop_name = prop_name
        self.prop_val = prop_val

    def __same__(self, o):
        if type(self) is not type(o):
            return False
        if not same(self.prop_type, o.prop_type):
            return False
        if not same(self.prop_name, o.prop_name):
            return False
        s_val, o_val = self.prop_val, o.prop_val
        if isinstance(self.prop_type, QOMPropertyTypeLink):
            s_val, o_val = idon(s_val), idon(o_val)
        if same(s_val, o_val):
            return True
        return False

