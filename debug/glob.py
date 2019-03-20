# A wrappers for global source level entities of DWARF info (like functions and
# global variables).

__all__ = [
    "Datum"
      , "SubprogDatum"
  , "Subprogram"
]

from elftools.dwarf.constants import (
    DW_INL_not_inlined
)
from common import (
    lazy,
    trie_find,
    intervalmap
)
from collections import (
    OrderedDict
)


class Datum(object):

    def __init__(self, dic, die):
        """
    :type dic: DWARFInfoCache
    :param dic:
        a global context

    :type die: elftools.dwarf.die.DIE
    :param die:
        the root of debug information entry tree describing that datum

        """
        self.dic = dic
        self.die = die

        self.name = die.attributes["DW_AT_name"].value

    # source code level terms

    @lazy
    def is_argument(self):
        return self.die.tag == "DW_TAG_formal_parameter"

    @lazy
    def is_variable(self):
        return self.die.tag == "DW_TAG_variable"

    @lazy
    def type(self):
        return self.dic.type_by_die(self.type_DIE)

    # assembly level terms

    @lazy
    def fetch_size(self):
        "Minimum bytes count that must be fetched to get entire datum."
        return self.type.size_expr

    @lazy
    def location(self):
        """ Location is a symbolic expression that can be used to get the value
of this datum at runtime.
        """
        try:
            loc = self.die.attributes["DW_AT_location"]
        except KeyError:
            return None

        if loc.form == "DW_FORM_exprloc":
            return self.dic.expr_builder.build(loc.value)
        else: # loc.form == "DW_FORM_loclistptr"
            raise NotImplementedError("location list")

    # DWARF specific

    @lazy
    def type_DIE(self):
        type_attr = self.die.attributes["DW_AT_type"]
        return self.dic.get_DIE_by_attr(type_attr, self.die.cu)


class SubprogDatum(Datum):

    def __init__(self, subprog, die):
        """
    :type subprog: Subprogram
    :param subprog:
        the subprogram containing this datum.

        """
        super(SubprogDatum, self).__init__(subprog.dic, die)
        self.subprog = subprog


SUBPROGRAM_DATUM_TAGS = set([
    "DW_TAG_variable",
    "DW_TAG_formal_parameter",
    "DW_TAG_constant"
])


class Subprogram(object):
    "Source level term. A function, method, procedure and so on..."

    def __init__(self, dic, die, name = None):
        """
    :type dic: DWARFInfoCache
    :param dic:
        a global context

    :type die: elftools.dwarf.die.DIE
    :param die:
        the root of debug information entry tree describing that subprogram

    :type name: str
    :param name:
        the name of this subprogram if it is already known. It's just an
        optimization of DIE attribute lookup

        """
        self.dic = dic
        self.die = die
        self.name = name or die.attributes["DW_AT_name"].value

    # source level terms

    @lazy
    def data(self):
        "Variables, parameters (arguments) and constants of the subprogram."
        data = OrderedDict()

        for die in self.die.iter_children():
            if die.tag not in SUBPROGRAM_DATUM_TAGS:
                continue

            datum = SubprogDatum(self, die)
            data[datum.name] = datum

        return data

    @lazy
    def type(self):
        "Type returned by the subprogram."
        die = self.die

        try:
            type_attr = die.attributes["DW_AT_type"]
        except KeyError:
            # It is likely that a type is requested for a value returned by the
            # subprogram. Hence, the subprogram likely has "DW_AT_type"
            # attribute. "try-except" is faster than "if-in" when a key is
            # likely exists in a `dict`.
            return None

        dic = self.dic

        type_die = dic.get_DIE_by_attr(type_attr, die.cu)

        return dic.type_by_die(type_die)

    # assembly level terms

    @lazy
    def line_map(self):
        """ Mapping from addresses to line program entries (DWARF) describing
source code of that subprogram.
        """
        die = self.die
        attrs = die.attributes

        if "DW_AT_decl_file" in attrs:
            decl_file = die.attributes["DW_AT_decl_file"].value
        else:
            decl_file = 0

        if not decl_file:
            raise ValueError("No source file has been specified")

        if "DW_AT_decl_line" in attrs:
            decl_line = die.attributes["DW_AT_decl_line"].value
        else:
            decl_line = 0

        if not decl_line:
            raise ValueError("No source line has been specified")

        dic = self.dic

        source_path = dic.get_CU_files(die.cu)[decl_file - 1]

        rpath = tuple(reversed(source_path))

        # line program for the CU must be already accounted by `get_CU_files`
        lm, _ = trie_find(dic.srcmap, rpath)

        ranges = self.ranges

        line_map = intervalmap()

        cur = decl_line
        while cur:
            entries = lm[cur]

            for e in entries:
                addr = e.state.address
                for l, h in ranges:
                    if l <= addr and addr < h:
                        break
                else:
                    # Address is not within the subroutine.
                    continue
                # At least one address is within the subroutine
                break
            else:
                # All entries are outside the subroutine address ranges.
                # `cur`rent line is after the subroutine. Hence, consequent
                # lines are too.
                break

            _next = lm.right_bound(cur)
            line_map[cur:_next] = entries
            cur = _next

        return line_map

    @lazy
    def prologues(self):
        """ Addresses of ends of this subprogram prologues. There are several
prologues possible.
        """

        ret = []
        line_map = self.line_map

        for entries in line_map.values():
            for e in entries:
                state = e.state
                if state.prologue_end:
                    ret.append(state.address)

        if not ret:
            # XXX: If no prologue explicitly specified then assume first line
            # is the prologue
            entries = line_map._items[0]
            ret.extend(e.state.address for e in entries)

        return ret

    @lazy
    def epilogues(self):
        """ Addresses of starts of this subprogram epilogues. There are several
epilogues possible.
        """

        ret = []
        line_map = self.line_map

        for entries in line_map.values():
            for e in entries:
                state = e.state
                if state.epilogue_begin:
                    ret.append(state.address)

        if not ret:
            # XXX: If no epilogue explicitly specified then assume last line
            # is the epilogue
            entries = line_map._items[-1]
            ret.extend(e.state.address for e in entries)

        return ret

    @lazy
    def inline(self):
        "Values greater than 0 means that the subprogram is inlined."
        attrs = self.die.attributes
        if "DW_AT_inline" in attrs:
            return attrs["DW_AT_inline"].value
        return DW_INL_not_inlined

    @lazy
    def ranges(self):
        """ Addresses occupied by the subprogram.

    :returns:
        an iterable of address ranges, tuples

        """

        attrs = self.die.attributes

        if "DW_AT_ranges" in attrs:
            # ranges_attr = attrs["DW_AT_ranges"]

            raise NotImplementedError()
        elif "DW_AT_low_pc" in attrs:
            low = attrs["DW_AT_low_pc"].value

            high_attr = attrs["DW_AT_high_pc"]
            if high_attr.form == "DW_FORM_addr":
                high = high_attr.value
            else:
                high = low + high_attr.value

            return ((low, high),)
        else:
            return None

    @lazy
    def frame_base(self):
        """ Location of frame base address. It's used to access this subprogram
stack at runtime.
        """

        fb = self.die.attributes["DW_AT_frame_base"]

        if fb.form == "DW_FORM_exprloc":
            return self.dic.expr_builder.build(fb.value)
        else: # loc.form == "DW_FORM_loclistptr"
            raise NotImplementedError("location list")

