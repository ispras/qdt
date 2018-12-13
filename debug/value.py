# Model of runtime values from debug session
__all__ = [
    "Value"
]

from common import (
    lazy
)
from .expression import (
    Register,
    Constant,
    AddressSize,
    Deref,
    ObjDeref,
    Mul,
    Plus
)
from .glob import (
    Datum
)
from .type import (
    Field,
    TYPE_CODE_PTR,
    TYPE_CODE_ARRAY,
    TYPE_CODE_STRUCT
)
from six import (
    integer_types
)
from traceback import (
    print_exc
)
from collections import (
    deque
)


class ArtificialPointer(object):
    """ Used internally for explicit casting. It emulates normal pointer which
is described by a `Type` instance.
    """

    def __init__(self, target_type):
        self.target_type = target_type
        self.code = TYPE_CODE_PTR


class ValueCast(object):
    """ A wrapper for `Value` instance that has been casted to another type.
Used internally. It emulates `Datum`. """

    def __init__(self, dic, datum, _type):
        self.dic = dic
        self.type = _type

        self._backing = datum

    @lazy
    def location(self):
        return self._backing.datum.location


class GlobalValue(object):
    """ A wrapper for `Value` instance that has been converted to global and
now represents a long-living value. Its memory location has been evaluated and
saved as constant. See `Value.to_global`. Used internally. It emulates `Datum`.
    """

    def __init__(self, datum, location):
        self.location = location

        self._backing = datum

    @lazy
    def dic(self):
        return self._backing.dic

    @lazy
    def type(self):
        return self._backing.type


class DereferencedValue(object):
    """ A wrapper for `Value` instance that has been dereferenced as a pointer
or indexed as an array. Its type is dereferenced too and its location
expression is extended correspondingly. See `Value.dereference` or
`Value.get_array_element`. Used internally. It emulates `Datum`.
    """

    def __init__(self, location, _type, reference):
        self.location = location
        self.type = _type

        self._backing = reference

    @lazy
    def dic(self):
        return self._backing.dic


class Returned(object):
    """ Wrapper for data returned by a subprogram. It has no location in memory
because subprograms normally returns values through a register. `expression`
attribute stores the rule to obtain the data itself. Used internally. It
emulates `Datum`
     """

    def __init__(self, dic, reg_idx, inner_pc):
        self.expression = Register(reg_idx)
        self.location = None
        self.dic = dic
        # Evaluation of type is expensive while a user may just want to
        # get return value from the corresponding register. Just remember
        # program counter to be able to obtain type on demand.
        self._backing = inner_pc

    @lazy
    def type(self):
        return self.dic.subprogram(self._backing).type


class Value(object):
    "Represents runtime value of a datum."

    def __init__(self, datum, runtime = None, obj = None, version = None):
        """
    :type obj: Expression
    :param obj:
        The datum may be _inside_ another datum (struct, class, ...). Then
        the datum location is given relative to the container. This field
        contains location of that container.

    :type version: int
    :param version:
        Some values are expected to have short live interval.

        For instance, a value corresponding to a function argument
        (normally gotten from runtime by name) has a frame relative
        location. Hence, it should not be used after target execution was
        consequently stopped inside another function (or even in another
        place of the same function). The same goes for a value derived
        from such short-living value too.

        Runtime has a version counter which is incremented at each target
        resumption. A value of that counter is used to mark such short
        living values. A warning is issued when the value is being fetched
        from runtime of different version.

        Related: `to_global`
        """
        if not isinstance(datum,
            (Datum, Field, Returned, ValueCast, GlobalValue, DereferencedValue)
        ):
            raise ValueError("Not supported/implemented value type %s" % (
                type(datum.__name__)
            ))

        self.datum = datum
        self.runtime = runtime
        self.object = obj
        self.version = version

    def to_global(self):
        """ A global value is expected to have constant memory address and
"alive" after target resumption. It is designed to preserve a long-living value
 derived from short-living one by permanent evaluation of the location.

This also can be used to just optimize expensive location evaluations.

Note that a value may represent a stack variable which is a pointer to a global
value. The pointer is *not* long-living itself because it is on the stack and
likely will be overwritten by consequent calls.

Related: `dereference`
        """
        return Value(
            datum = GlobalValue(self, Constant(
                self.eval(self.datum.location)
            )),
            runtime = self.runtime
        )

    @property
    def is_global(self):
        return self.version is None

    def cast(self, name):
        dic = self.dic

        type_name = name.rstrip("*")
        pointer_depth = len(name) - len(type_name)

        t = dic[type_name.strip()]

        for _ in range(pointer_depth):
            t = ArtificialPointer(t)

        return Value(
            ValueCast(dic, self, t),
            runtime = self.runtime,
            obj = self.object,
            version = self.version
        )

    @lazy
    def dic(self):
        return self.datum.dic

    def eval(self, expr):
        rt = self.runtime

        # it is a value inside another value
        obj = self.object
        if obj is not None:
            rt.push(obj)

        loc = expr.eval(rt)

        if obj is not None:
            rt.pop()

        return loc

    def fetch(self, size = None):
        datum = self.datum
        loc_expr = datum.location

        version = self.version
        if version is not None and version != self.runtime.version:
            print("Fetching short-living value from advanced runtime.")

        if loc_expr is None:
            expr = datum.expression
        else:
            if size is None:
                size = self.type.size_expr
            expr = Deref(loc_expr, size)

        fetched = self.eval(expr)

        return fetched

    def fetch_pointer(self):
        remote = self.runtime.target

        return self.fetch(remote.address_size)

    def fetch_c_string(self, limit = 10):
        """
        Reads C-string from remote.

        :type limit: int
        :param limit:
            is maximum count of memory blocks (64 bytes in each). If the limit
            is exceeded then it is likely that the pointer refers to something
            that differs from C string. A user should give a bigger value (or
            something that never equal to `int`, like `None`) if string is
            expected to be very long.
        :returns: `str`
        """

        addr = self.fetch_pointer()
        if addr:
            value = deque()
            pos = -1
            dump = self.runtime.target.dump

            while pos == -1:
                if len(value) == limit:
                    raise RuntimeError("C string length limit exceeded")

                try:
                    substring = dump(64, addr)
                except RuntimeError:
                    # XXX: a workaround for a non-deterministic E01 error from
                    # gdb stub because of an unidentified reason
                    print("Failed to fetch string.")
                    print_exc()
                    break

                pos = substring.find("\0")
                if pos != -1:
                    substring = substring[:pos]
                value.append(substring)
                addr = addr + 64

            return "".join(value)
        else:
            # NULL pointer dereference
            return None

    @lazy
    def type(self):
        return self.datum.type

    def dereference(self):
        _type = self.type
        while _type.code != TYPE_CODE_PTR:
            _type = _type.target_type

        datum = self.datum

        location = datum.location
        if location is None:
            # pointer should by given by an expression
            location = datum.expression
        else:
            # pointer is in target memory and should be fetched
            location = Deref(location, AddressSize())

        return Value(
            DereferencedValue(location, _type.target_type, self),
            runtime = self.runtime,
            obj = self.object,
            version = self.version
        )

    @lazy
    def address(self):
        return self.eval(self.datum.location)

    def __getitem__(self, name):
        if isinstance(name, integer_types):
            return self.get_array_element(name)
        else:
            return self.get_field(name)

    def get_array_element(self, index):
        _type = self.type

        el_type = _type.target_type

        datum = self.datum
        location = datum.location

        code = _type.code
        if code == TYPE_CODE_PTR:
            el_size = el_type.size_expr
            if location is None:
                # pointer should by given by an expression
                location = datum.expression
            else:
                # pointer is to the first element of the array,
                # it's to be fetched first to get the element's position.
                location = Deref(location, AddressSize())
        elif code == TYPE_CODE_ARRAY:
            attrs = _type.die.attributes
            if "DW_AT_byte_stride" in attrs:
                el_size = attrs["DW_AT_byte_stride"].value
            elif "DW_AT_bit_stride" in attrs:
                stride = attrs["DW_AT_bit_stride"].value
                if stride & 7:
                    raise NotImplementedError(
                        "array stride is not byte aligned"
                    )
                el_size = stride >> 3
            else:
                el_size = el_type.size_expr
            # Note that array's location is the location of its first element
        else:
            raise ValueError("Cannot get array element of type %u" % code)

        # add offset to the first array element location
        location = Plus(location, Mul(el_size, index))

        return Value(
            DereferencedValue(location, el_type, self),
            runtime = self.runtime,
            obj = self.object,
            version = self.version
        )

    def get_field(self, name):
        _type = self.type
        datum = self.datum

        location = datum.location

        # TODO: support unions
        while _type.code != TYPE_CODE_STRUCT:
            # Implicit pointer dereferencing simplifies reading of structure
            # fields by the structure pointer.
            if _type.code == TYPE_CODE_PTR:
                # see `dereference` method for explanation
                if location is None:
                    location = datum.expression
                else:
                    location = Deref(location, AddressSize())
            _type = _type.target_type

        # XXX: if `location` is `None` here then `self` is a non-pointed value
        # of a container itself and `datum.expression` should hold whole that
        # container. Moreover this means, the container does not resides in
        # target memory. It is possible to place a small structure in a target
        # register but it is likely that a user made a mistake during casting
        # and looking for a member in something that is not a container. Hence,
        # getting member is not implemented for this case.

        obj = self.object
        if obj:
            location = ObjDeref(obj, location)

        field = _type[name]

        return Value(field, self.runtime,
            obj = location,
            version = self.version
        )

