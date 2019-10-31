# Useful links:
# https://docs.python.org/3/library/dis.html
# https://github.com/scipy/weave/blob/master/weave/bytecodecompiler.py

from sys import (
    version_info
)

print("version_info=%s" % (version_info,))

from dis import (
    get_instructions
)
from types import (
    FunctionType,
    LambdaType
)
from source import *

def neg_(a):
    return -a

def bnot_(a):
    return ~a

def lnot_(a):
    return not a

def yield_(a):
    yield a

def add_(a, b):
    return a + b

def inc_(a):
    a += 1
    return a

def inv_v2_(a):
    a = a + 1
    return a

def dict_set_(a):
    a[0] = 1

def set_add_(a, b):
    set.add(a, b)

def max_(a, b):
    if a < b:
        return b
    else:
        return a

def max_v2_(a, b):
    if a < b:
        ret = b
    else:
        ret = a

    return ret


REG_FLAGS = 10
FLAG_Z = 1 << 4

class CPU(object):

    def mul(self, dst, src):
        res = self.regs[dst] * self.regs[src]
        self.regs[dst] = res
        if res:
            self.regs[REG_FLAGS] &= ~FLAG_Z
        else:
            self.regs[REG_FLAGS] |= FLAG_Z

    def ror(self, dst, src):
        res = ror(self.regs[dst], self.regs[src])
        self.regs[dst] = res
        if res:
            self.regs[REG_FLAGS] &= ~FLAG_Z
        else:
            self.regs[REG_FLAGS] |= FLAG_Z


cpu_mul_ = CPU.mul
cpu_ror_ = CPU.ror


def py2i3s(inst_method):

    void_t = Type("void", base = True)
    p_void_t = Pointer(void_t)
    int_t = Type("int", base = True, incomplete = False)
    p_int_t = Pointer(int_t)
    cpu_t = Structure("CPU", p_int_t.gen_var("regs"))
    p_cpu_t = Pointer(cpu_t)

    NULL = Macro("NULL")

    func = BodyTree()
    cpu = p_cpu_t.gen_var("cpu")

    def ror(arg2, arg1):
        return OpRotR(arg1, arg2)

    globs = dict(
        ror = ror
    )

    code = inst_method.__code__

    variables = {}
    for name in code.co_varnames:
        if name == "self":
            variables[name] = cpu
        else:
            variables[name] = int_t.gen_var(name)

    stack = []
    blocks = [func]

    def LOAD_FAST(i):
        var_num = i.arg
        varname = code.co_varnames[var_num]
        stack.append(variables[varname])

    def LOAD_ATTR(i):
        namei = i.arg
        container = stack.pop()
        deref = OpSDeref(container, code.co_names[namei])
        stack.append(deref)

    def BINARY_SUBSCR(_):
        index = stack.pop()
        array = stack.pop()
        value = OpIndex(array, index)
        stack.append(value)

    def STORE_SUBSCR(_):
        index = stack.pop()
        array = stack.pop()
        val = stack.pop()
        blocks[-1](OpAssign(OpIndex(array, index), val))

    def BINARY_MULTIPLY(_):
        right = stack.pop()
        left = stack.pop()
        res = OpMul(left, right)
        stack.append(res)

    def BINARY_ADD(_):
        right = stack.pop()
        left = stack.pop()
        res = OpAdd(left, right)
        stack.append(res)

    def INPLACE_AND(_):
        right = stack.pop()
        left = stack.pop()
        res = OpAnd(left, right)
        stack.append(res)

    def INPLACE_OR(_):
        right = stack.pop()
        left = stack.pop()
        res = OpOr(left, right)
        stack.append(res)

    def STORE_FAST(i):
        var_num = i.arg
        val = stack.pop()
        varname = code.co_varnames[var_num]
        blocks[-1](OpAssign(variables[varname], val))

    def LOAD_GLOBAL(i):
        namei = i.arg
        name = code.co_names[namei]
        try:
            val = globs[name]
        except KeyError:
            try:
                val = Type[name]
            except TypeNotRegistered:
                glob_val = globals()[name]
                val = Macro(name, text = str(glob_val))

        stack.append(val)

    def CALL_FUNCTION(i):
        argc = i.arg
        args = stack[-argc:]
        func = stack[-argc - 1]
        del stack[-argc - 1:]
        if isinstance(func, FunctionType):
            res = func(*args)
        else:
            res = Call(func, *args)
        stack.append(res)

    def DUP_TOP_TWO(_):
        stack.extend(stack[-2:])

    def ROT_THREE(_):
        stack.insert(-2, stack.pop())

    def UNARY_INVERT(_):
        stack.append(OpNot(stack.pop()))

    def POP_JUMP_IF_FALSE(_):
        stack.pop() # TODO

    def LOAD_CONST(i):
        consti = i.arg
        const = code.co_consts[consti]
        stack.append(const)

    def RETURN_VALUE(_):
        blocks[-1](Return(stack.pop()))

    locs = dict(locals())

    for i in get_instructions(inst_method):
        print([str(v) for v in stack])
        print(i.opname, i.argval)
        try:
            handler = locs[i.opname]
        except KeyError:
            print("Unsupported opcode " + i.opname)
            continue

        handler(i)

    if stack:
        print("stack has unused values")
        for expr in reversed(stack):
            print(expr)
    """
    body = []
    for expr in stack:
        if isinstance(expr, Node):
            body.append(expr)

    func(*list(reversed(body)))
    """

    print(str(func))

DISASSEMBLABLE = set([
    FunctionType,
    LambdaType
])

def main():
    globs = list(globals().items())

    with open(__file__, "r") as f:
        code = f.read()

    lines = code.splitlines()

    for n, v in globs:
        if n[-1] != "_":
            continue
        if type(v) not in DISASSEMBLABLE:
            continue

        prev_line = v.__code__.co_firstlineno

        print("Disassembling " + n)
        for i in get_instructions(v):

            l = i.starts_line
            if l:
                for ln in range(prev_line, l + 1):
                    print("%04d: %s" % (ln, lines[ln - 1]))
                prev_line = l + 1

            print("    | %i %i(%s) %s" % (i.offset, i.opcode, i.opname, i.argval))

        print("") # delimeter

    py2i3s(cpu_ror_)


if __name__ == "__main__":
    exit(main() or 0)
