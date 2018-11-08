# High level model of source cold level types from DWARF information

__all__ = [
    "Type"
  , "Field"

  , "TYPE_TAGS"
  , "TYPE_CODE_PTR"
  , "TYPE_CODE_ARRAY"
  , "TYPE_CODE_STRUCT"
  , "TYPE_CODE_UNION"
  , "TYPE_CODE_ENUM"
  , "TYPE_CODE_FLAGS"
  , "TYPE_CODE_FUNC"
  , "TYPE_CODE_INT"
  , "TYPE_CODE_FLT"
  , "TYPE_CODE_VOID"
  , "TYPE_CODE_SET"
  , "TYPE_CODE_RANGE"
  , "TYPE_CODE_STRING"
  , "TYPE_CODE_BITSTRING"
  , "TYPE_CODE_ERROR"
  , "TYPE_CODE_METHOD"
  , "TYPE_CODE_METHODPTR"
  , "TYPE_CODE_MEMBERPTR"
  , "TYPE_CODE_REF"
  , "TYPE_CODE_RVALUE_REF"
  , "TYPE_CODE_CHAR"
  , "TYPE_CODE_BOOL"
  , "TYPE_CODE_COMPLEX"
  , "TYPE_CODE_TYPEDEF"
  , "TYPE_CODE_NAMESPACE"
  , "TYPE_CODE_DECFLOAT"
  , "TYPE_CODE_INTERNAL_FUNCTION"
]

from common import (
    lazy
)
from .expression import (
    Plus,
    ObjectAddress,
    AddressSize
)
from itertools import (
    count
)
from collections import (
    OrderedDict
)


class Field(object):
    """ Describes a field of a container (like C `struct`). """

    def __init__(self, container, die):
        self.container = container
        self.die = die

        self.name = die.attributes["DW_AT_name"].value

    # source code level terms

    @lazy
    def type(self):
        die = self.die
        dic = self.container.dic

        type_attr = die.attributes["DW_AT_type"]
        type_die = dic.get_DIE_by_attr(type_attr, die.cu)

        return dic.type_by_die(type_die)

    # assembly level terms

    @lazy
    def location(self):
        """ Location is a symbolic expression that can be used to get the value
of this field at runtime.
        """
        attrs = self.die.attributes
        if "DW_AT_data_member_location" in attrs:
            loc_attr = attrs["DW_AT_data_member_location"]
            # location list is not expected there
            if loc_attr.form == "DW_FORM_exprloc":
                return self.container.dic.expr_parser.build(loc_attr.value)
            else: # integer constant
                return Plus(ObjectAddress(), loc_attr.value)
        elif "DW_AT_data_bit_offset" in attrs:
            # See DWARF3, p.88 (PDF p. 102)
            raise NotImplementedError("Bit offset of fields")
        else:
            return ObjectAddress()

    # DWARF specific

    @property
    def dic(self):
        return self.container.dic


# TODO: assign values according to GDB Python API
c = count(1)

TYPE_CODE_PTR = next(c)
TYPE_CODE_ARRAY = next(c)
TYPE_CODE_STRUCT = next(c)
TYPE_CODE_UNION = next(c)
TYPE_CODE_ENUM = next(c)
TYPE_CODE_FLAGS = next(c)
TYPE_CODE_FUNC = next(c)
TYPE_CODE_INT = next(c)
TYPE_CODE_FLT = next(c)
TYPE_CODE_VOID = next(c)
TYPE_CODE_SET = next(c)
TYPE_CODE_RANGE = next(c)
TYPE_CODE_STRING = next(c)
TYPE_CODE_BITSTRING = next(c)
TYPE_CODE_ERROR = next(c)
TYPE_CODE_METHOD = next(c)
TYPE_CODE_METHODPTR = next(c)
TYPE_CODE_MEMBERPTR = next(c)
TYPE_CODE_REF = next(c)
TYPE_CODE_RVALUE_REF = next(c)
TYPE_CODE_CHAR = next(c)
TYPE_CODE_BOOL = next(c)
TYPE_CODE_COMPLEX = next(c)
TYPE_CODE_TYPEDEF = next(c)
TYPE_CODE_NAMESPACE = next(c)
TYPE_CODE_DECFLOAT = next(c)
TYPE_CODE_INTERNAL_FUNCTION = next(c)

del c

tag2code = {
    "DW_TAG_pointer_type" : TYPE_CODE_PTR,
    "DW_TAG_array_type" : TYPE_CODE_ARRAY,
    "DW_TAG_structure_type": TYPE_CODE_STRUCT,
    "DW_TAG_typedef": TYPE_CODE_TYPEDEF,
    "DW_TAG_union_type" : TYPE_CODE_UNION
}

TYPE_MODIFIER_TAGS = set([
# Not all format defined type modifiers are here because pointer & reference
# modifiers are handled as types.
    "DW_TAG_const_type",
    "DW_TAG_packed_type",
    "DW_TAG_restrict_type",
    "DW_TAG_shared_type",
    "DW_TAG_volatile_type"
])

TYPE_TAGS = set()
TYPE_TAGS.update(tag[7:] for tag in TYPE_MODIFIER_TAGS)
TYPE_TAGS.update(tag[7:] for tag in tag2code)


class Type(object):
    """ Describes source level type recovered from DWARF info """

    def __init__(self, dic, die):
        """
    :param dic:
        DWARFInfoCache, a global context
    :param die:
        is the Debugging Information Entry describing this type. It`s an
        instance of `elftools.ddwarf.die.DIE`

        """
        self.dic = dic

        tag = die.tag

        if tag in TYPE_MODIFIER_TAGS:
            self.first_modifier = die

            modifiers = set()
            die_getter = dic.get_DIE_by_attr

            while True:
                # truncate "DW_TAG_" prefix and "_type" suffix
                mod = tag[7:-5]

                modifiers.add(mod)
                die = die_getter(die.attributes["DW_AT_type"], die.cu)
                tag = die.tag
                if tag not in TYPE_MODIFIER_TAGS:
                    break

            self.modifiers = modifiers
        else:
            self.modifiers = self.first_modifier = None

        self.tag = tag
        self.die = die

        if tag in tag2code:
            self.code = tag2code[tag]
        else:
            # is not implemented yet
            self.code = None

    # source code level terms

    @lazy
    def declaration(self):
        return "DW_AT_declaration" in self.die.attributes

    @lazy
    def members(self):
        members = OrderedDict()

        for c in self.die.iter_children():
            if c.tag != "DW_TAG_member":
                continue
            f = Field(self, c)
            members[f.name] = f

        return members

    def fields(self):
        """ In GDB`s implementation this name corresponds to a method. Hence,
it is a method here. But it is just a proxy for the `members` "lazy" attribute.
        """
        return self.members.values()

    @lazy
    def name(self):
        """
    :returns:
        name of this type in source code.

        """
        attrs = self.die.attributes
        if "DW_AT_name" in attrs:
            return attrs["DW_AT_name"].value
        return None

    def target(self):
        """ In GDB`s implementation this name corresponds to a method. Hence,
it is a method here. But it is just a proxy for the `target_type` "lazy"
attribute.
        """
        return self.target_type

    @lazy
    def target_type(self):
        "An inner type of some types like pointer, 'typedef' or array."
        die = self.die
        dic = self.dic

        type_attr = die.attributes["DW_AT_type"]
        type_die = dic.get_DIE_by_attr(type_attr, die.cu)

        return dic.type_by_die(type_die)

    # DWARF specific

    @lazy
    def size_expr(self):
        """
    :returns:
        a symbolic expression representing in-memory size of this type
        """
        code = self.code
        if code == TYPE_CODE_PTR:
            return AddressSize()
        elif code == TYPE_CODE_TYPEDEF:
            return self.target_type.size_expr
        else:
            raise NotImplementedError(
                "Unknown size of type with code %u" % code
            )
