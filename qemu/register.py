__all__ = [
    "OpaqueRegister"
      , "Register"
]

from common import (
    same_attrs,
)
from .qtn import (
    QemuTypeName,
)
from source import (
    CINT,
    CSTR,
)
from source.function import (
    Call,
    Comment,
    MCall,
    OpAdd,
    OpAddr,
    OpAnd,
    OpAssign,
    OpNot,
    OpOr,
    OpSDeref,
    OpSub,
    StrConcat,
    SwitchCase,
)

from math import (
    log
)


class OpaqueRegister(object):

    def __init__(self, size, name):
        self.size, self.name = size, name


class Register(OpaqueRegister):

    def __init__(self, size,
        name = None,
        access = "rw",
        reset = 0,
        full_name = None,
        wmask = None,
        warbits = None
    ):
        """
@param size: of the register in bytes.
@param name: is a base for names of generated entities.
    `None` or "gap" named registers are not backed by a state field.
@param access: defines how `MemoryRegionOps`'s callbacks will handle access
    to the register.
    Implemented chars: 'w', 'r'
@param reset: value for the register.
    `None` means the register is not being reset.
@param full_name: pretty string used in generated comments.
@param wmask: (write mask) selects bits which can be written.
    `None` corresponds to 0b11...11. I.e. all bits are writable.
@param warbits: (Write-After-Read (WAR) bit mask) selects which bits can only
    be written after a read access to that register.
    Only bits selected by `wmask` can be written anyway.
    `None` corresponds to 0b00...00, all bits can be written without reading.
    Disabling of WAR bits for writing again is responsibility of semantic
    code.
        """
        super(Register, self).__init__(size, name)
        self.access = access
        if reset is None:
            self.reset = None
        else:
            if size <= 8:
                self.reset = CINT(reset, 16, size * 2)
            else:
                # TODO: support C-string as reset value (set using memcpy)
                self.reset = CINT(reset, 16, 1)

        self.full_name = full_name

        if wmask is None:
            wmask = (1 << (size * 8)) - 1
        self.wmask = CINT(wmask, 2, size * 8)

        if warbits is None:
            warbits = 0
        self.warbits = CINT(warbits, 2, size * 8)

    def __same__(self, o):
        if not isinstance(o, Register):
            return False
        return same_attrs(self, o, "name", "access", "reset", "full_name",
            "wmask", "warbits"
        )

    def __repr__(self, *args, **kwargs):
        # TODO: adapt and utilize PyGenerator.gen_args for this use case

        ret = type(self).__name__
        size = self.size

        ret += "(" + repr(size)

        name = self.name
        if name is not None:
            ret += ", name = " + repr(name)

        access = self.access
        if access != "rw":
            ret += ", access = " + repr(access)

        reset = self.reset
        if reset != CINT(0, 16, size * 2):
            ret += ", reset = " + repr(reset)

        fn = self.full_name
        if fn is not None:
            ret += ", full_name = " + repr(fn)

        wm = self.wmask
        if (wm.v != (1 << (size * 8)) - 1
        or  wm.b != 2
        or  wm.d != size * 8
        ):
            ret += ", wmask = " + repr(wm)

        warb = self.warbits
        if (warb.v != 0
        or  warb.b != 2
        or  warb.d != size * 8
        ):
            ret += ", warbits = " + repr(warb)

        ret += ")"
        return ret


def get_reg_range(regs):
    return sum(reg.size for reg in regs)


def gen_reg_cases(regs, access, offset_name, val, ret, acc_size, s):
    reg_range = get_reg_range(regs)
    cases = []
    digits = int(log(reg_range, 16)) + 1

    offset = 0

    for reg in regs:
        size = reg.size

        name = reg.name
        if name is None or name == "gap":
            offset += size
            continue

        offset_literal = CINT(offset, base = 16, digits = digits)

        if size == 1:
            case_cond = offset_literal
        else:
            case_cond = (
                offset_literal,
                CINT(offset + size - 1, base = 16, digits = digits)
            )
        offset += size

        case = SwitchCase(case_cond)

        comment = name
        if reg.full_name: # neither `None` nor empty string
            comment += ", " + reg.full_name

        case(Comment(comment))

        if access in reg.access:
            qtn = QemuTypeName(name)
            s_deref_war = lambda : OpSDeref(
                s,
                qtn.for_id_name + "_war"
            )
            s_deref = OpSDeref(
                s,
                qtn.for_id_name
            )

            if access == "r":
                if size <= 8:
                    case(OpAssign(
                        ret,
                        s_deref
                    ))

                    warb = reg.warbits
                    if warb.v: # neither None nor zero
                        # There is at least one write-after-read
                        # bit in the reg.
                        wm = reg.wmask
                        if wm.v == (1 << (size * 8)) - 1:
                            # no read only bits: set WAR mask to 0xF...F
                            case(
                                OpAssign(
                                    s_deref_war(),
                                    OpNot(0)
                                )
                            )
                        else:
                            # writable bits, read only bits: init WAR mask with
                            # write mask
                            case(
                                OpAssign(
                                    s_deref_war(),
                                    wm
                                )
                            )
                else:
                    field_offset = OpSub(
                        offset_name,
                        offset_literal,
                        parenthesis = True
                    )
                    case(OpAssign(
                        acc_size,
                        MCall("MIN", acc_size, OpSub(size, field_offset))
                    ))
                    case(Call(
                        "memcpy",
                        OpAddr(ret),
                        OpAdd(s_deref, field_offset),
                        acc_size
                    ))

                    # TODO: support write-after-read bits for long buffers

            elif access == "w":
                if size <= 8:
                    wm = reg.wmask
                    warb = reg.warbits

                    if warb.v and wm.v:
                        # WAR bits, writable, read only bits: use WAR mask as
                        # dynamic write mask
                        case(
                            OpAssign(
                                s_deref,
                                OpOr(
                                    OpAnd(
                                        val,
                                        s_deref_war(),
                                        parenthesis = True
                                    ),
                                    OpAnd(
                                        s_deref,
                                        OpNot(
                                            s_deref_war()
                                        ),
                                        parenthesis = True
                                    )
                                )
                            )
                        )
                    elif wm.v == (1 << (size * 8)) - 1:
                        # no WAR bits, no read only bits
                        # write mask does not affect the value being assigned
                        case(
                            OpAssign(
                                s_deref,
                                val
                            )
                        )
                    elif wm.v:
                        # no WAR bits, writable bits,
                        # read only bits: use static
                        # write mask
                        case(
                            OpAssign(
                                s_deref,
                                OpOr(
                                    OpAnd(
                                        val,
                                        wm,
                                        parenthesis = True
                                    ),
                                    OpAnd(
                                        s_deref,
                                        OpNot(
                                            wm
                                        ),
                                        parenthesis = True
                                    )
                                )
                            )
                        )
                else:
                    field_offset = OpSub(
                        offset_name,
                        offset_literal,
                        parenthesis = True
                    )
                    case(OpAssign(
                        acc_size,
                        MCall("MIN", acc_size, OpSub(size, field_offset))
                    ))
                    case(Call(
                        "memcpy",
                        OpAdd(s_deref, field_offset),
                        OpAddr(val),
                        acc_size
                    ))

                    # TODO: support write-after-read bits for long buffers
        else:
            case(
                Call(
                    "fprintf",
                    MCall("stderr"),
                    StrConcat(
                        CSTR(
"%%s: %s 0x%%0%d" % ("Reading from" if access == "r" else "Writing to", digits)
                        ),
                        MCall("HWADDR_PRIx"),
                        CSTR("\\n"),
                        delim = "@s"
                    ),
                    MCall("__func__"),
                    offset_name
                )
            )

        cases.append(case)

    return cases
