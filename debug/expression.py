# A model of symbolic expressions cowers DWARF location expressions

__all__ = [
   "Expression"
      , "Shr"
      , "Abs"
      , "Neg"
      , "Not"
      , "Dup"
      , "Register"
      , "FrameBase"
      , "AddressSize"
      , "Deref"
      , "ObjDeref"
      , "ObjectAddress"
      , "ToTLS"
      , "CFA"
      , "Constant"

      # Defined dynamically using `exec`
      , "And"
      , "Div"
      , "Minus"
      , "Mod"
      , "Mul"
      , "Or"
      , "Plus"
      , "Shl"
      , "Shra"
      , "Xor"
      , "Le"
      , "Ge"
      , "Eq"
      , "Lt"
      , "Gt"
      , "Ne"

  # list of dynamically defined `Expression` subclasses
  , "DWARF_BINATY_OPS"
]


class Expression(object):
    """ An expression that can be evaluated during debug session. It's an
acyclic graph like construct. Any `Expression` instance keeps references
(`refs`) to other `Expression` instances those values are required for this
one to be evaluated.
    """

    def __init__(self, *refs):
        self.refs = refs

    def __eval_recursively__(self, runtime, values):
        refs = self.refs

        args = []

        for ref in refs:
            if isinstance(ref, Expression):
                if ref in values:
                    args.append(values[ref])
                else:
                    args.append(ref.__eval_recursively__(runtime, values))
            else: # immediate value
                args.append(ref)

        if isinstance(self, Dup):
            val = args[-1]
        else:
            val = self.__eval__(*([runtime] + args))

        values[self] = val
        return val

    def eval(self, runtime):
        """ Evaluates the expression.

    :param runtime:
        a context of debug session
    :returns:
        evaluated value, a Python's `int` normally

        """
        return self.__eval_recursively__(runtime, {})

    def __eval__(self, runtime):
        # The `Expression` is an interface. It does not implement any actual
        # evaluation.
        raise NotImplementedError(str(self))


DWARF_BINATY_OPS = (
    ("and", "&"),
    ("div", "/"),
    ("minus", "-"),
    ("mod", "%"),
    ("mul", "*"),
    ("or", "|"),
    ("plus", "+"),
    ("shl", "<<"),
    ("shra", ">>"),
    ("xor", "^"),
    ("le", "<="),
    ("ge", ">="),
    ("eq", "=="),
    ("lt", "<"),
    ("gt", ">"),
    ("ne", "!=")
)

for op_name, oper in DWARF_BINATY_OPS:
    exec("""
class {name}(Expression):

    def __eval__(self, _, ref0, ref1):
        return ref1 {oper} ref0

    def __str__(self):
        return "(%s) {oper} (%s)" % (self.refs[1], self.refs[0])

""".format(name = op_name.title(), oper = oper)
    )


class Shr(Expression):

    def __eval__(self, _, ref0, ref1):
        # https://stackoverflow.com/questions/5832982/how-to-get-the-logical-right-binary-shift-in-python
        return (ref1 % 0x100000000) >> ref0

    def __str__(self):
        return "%s >>> %s" % (self.refs[1], self.refs[0])


class Abs(Expression):

    def __eval__(self, _, op):
        if op >= 0:
            return op
        else:
            return -op

    def __str__(self):
        return "|%s|" % self.refs[0]


class Neg(Expression):

    def __eval__(self, _, ref0):
        return -ref0

    def __str__(self):
        return "-%s" % self.refs[0]


class Not(Expression):

    def __eval__(self, _, ref0):
        return ~ref0

    def __str__(self):
        return "~%s" % self.refs[0]


class Dup(Expression):

    def __str__(self):
        return str(self.refs[0])


class Register(Expression):
    "Runtime value of a target register."

    def __str__(self):
        return "reg #%u" % self.refs[0]


class FrameBase(Expression):
    "Base address of current subprogram frame."

    def __str__(self):
        return "FRAME"


class AddressSize(Expression):
    "Size of address of target architecture."

    def __str__(self):
        return "sizeof(long)"


class Deref(Expression):

    def __init__(self, address, size, address_space = None):
        super(Deref, self).__init__(address, size, address_space)

    def __str__(self):
        return "mem[%s:%s + %s]" % (self.refs[0], self.refs[0], self.refs[1])


class ObjDeref(Expression):
    "Implements object stacking for chain of object-relative evaluations."

    def __str__(self):
        return "(%s) -> (%s)" % tuple(self.refs)


class ObjectAddress(Expression):
    """ Refers to top of object stack during object-relative evaluations.
See DW_OP_push_object_address operation description of DWARF.
    """

    def __str__(self):
        return "OBJECT"


class ToTLS(Expression):
    """ Translates value into an address in the current thread's thread-local
storage. See DW_OP_form_tls_address operation description.
    """

    def __str__(self):
        return "TLS[%s]" % self.refs[0]


class CFA(Expression):
    "Canonical Frame Address. See DW_OP_call_frame_cfa operation description."

    def __str__(self):
        return "CFA"


class Constant(Expression):
    """ This wrapper for a constant is designed to use a Python value outside
an `Expression` but in places where an `Expression` is expected by foreign
code. Note that Python integers can and must be used inside composite
expressions as-is without this wrapper.
    """

    def __str__(self):
        return str(self.refs[0])

    def __eval__(self, _, value):
        return value

