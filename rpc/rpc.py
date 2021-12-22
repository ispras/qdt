__all__ = [
    "rpc"
  , "get_stc"
  , "gen_global_rpc_types"
  , "iter_rpc"
  , "gen_rpc_impl_header"
      , "fill_rpc_impl_header"
  , "swap"
  , "RPCProtocol"
  , "simple_type_fmts"
  , "RPCFrontEnd"
  , "swap"
  , "fitting_fmt"
  , "RPCStreamConnection"
]

from collections import (
    OrderedDict,
)
from common import (
    lazy,
    SkipVisiting,
    StopVisiting,
)
from inspect import (
    getargspec,
    getmro,
)
from itertools import (
    count,
)
from functools import (
    wraps,
)
from source import (
    add_base_types,
    BodyTree,
    BranchElse,
    BranchIf,
    BranchSwitch,
    Break,
    Call,
    Comment,
    SwitchCase,
    SwitchCaseDefault,
    Declare,
    Enumeration,
    Function,
    Header,
    OpAdd,
    OpAddr,
    OpAssign,
    OpCast,
    OpCombAssign,
    OpDeclareAssign,
    OpDeref,
    OpMul,
    OpNEq,
    OpSDeref,
    OpSizeOf,
    OpSub,
    Pointer,
    Return,
    Source,
    SourceTreeContainer,
    Structure,
    Type,
    TypeReferencesVisitor,
    Variable,
)
from struct import (
    Struct,
)
from bisect import (
    insort,
)
from six import (
    text_type,
)


stc = None
def get_stc():
    global stc

    if stc is None:
        stc = SourceTreeContainer()
        with stc:
            gen_global_rpc_types()

    return stc


def gen_global_rpc_types():
    add_base_types()
    uint8_t = Type["uint8_t"]
    uint16_t = Type["uint16_t"]
    uint32_t = Type["uint32_t"]

    global NULL
    NULL = Type["NULL"]

    global void
    void = Type["void"]

    global rpc_h
    rpc_h = Header("rpc.h")

    # TODO: parse those from rpc.h or generate rpc.h entirely
    global RPCError
    RPCError = Enumeration([
            "RPC_ERR_NO",
            "RPC_ERR_READ",
            "RPC_ERR_WRITE",
            "RPC_ERR_ALLOC",
            "RPC_ERR_UNIMPL_CALL",
            "RPC_ERR_BACKEND",
            "RPC_ERR_COUNT"
        ],
        typedef_name = "RPCError"
    )
    rpc_h(RPCError)

    global rpc_ptr_t
    rpc_ptr_t = Pointer(void, name = "rpc_ptr_t")
    rpc_h(rpc_ptr_t)

    global RPCBackEnd
    RPCBackEnd = Pointer(void, name = "RPCBackEnd")
    rpc_h(RPCBackEnd)

    global rpc_backend_handle_message
    rpc_backend_handle_message = Function(
        name = "rpc_backend_handle_message",
        ret_type = RPCError,
        args = [
            RPCBackEnd("be"),
            rpc_ptr_t("ctx"),
            rpc_ptr_t("msg"),
            uint32_t("msg_size"),
            Pointer(Pointer(uint8_t))("response"),
            Pointer(uint32_t)("response_size")
        ]
    )
    rpc_h(rpc_backend_handle_message)

    global rpc_backend_alloc_response
    rpc_backend_alloc_response = Function(
        name = "rpc_backend_alloc_response",
        ret_type = RPCError,
        args = [
            RPCBackEnd("be"),
            uint32_t("response_size"),
            Pointer(rpc_ptr_t)("response")
        ]
    )
    rpc_h(rpc_backend_alloc_response)

    global RPCBuffer
    RPCBuffer = Structure("RPCBuffer",
        uint16_t("size"),
        Pointer(uint8_t)("data"),
    )
    rpc_h(RPCBuffer)

    global RPCString
    RPCString = Structure("RPCString",
        uint16_t("length"),
        Pointer(uint8_t)("data"),
    )
    rpc_h(RPCString)

    global memcpy
    memcpy = Type["memcpy"]


class RPCOpsGenVisitor(TypeReferencesVisitor):

    def __init__(self, t, *a, **kw):
        super(RPCOpsGenVisitor, self).__init__(
            # `root` is not visited. So, wrap `t`ype in a container because
            # it can be a type `on_visit` is looking for.
            [t],
            *a, **kw
        )
        self._ops = []

    def iter_ops(self):
        del self._ops[:]
        self.visit()
        return iter(self._ops)

    def __iter__(self):
        return self.iter_ops()


class RPCBufferCounter(RPCOpsGenVisitor):

    @lazy
    def total(self):
        self._total = 0
        self.visit()
        try:
            return self._total
        finally:
            del self._total

    def on_visit(self):
        if self.cur is RPCBuffer or self.cur is RPCString:
            self._total += 1
            raise StopVisiting


class RPCBufferVisitor(RPCOpsGenVisitor):

    def __init__(self, root_val, *a, **kw):
        super(RPCBufferVisitor, self).__init__(*a, **kw)
        self._root_val = root_val

    @property
    def deref_root_val(self):
        res = self._root_val
        for i in self.path:
            o = i[0]
            if isinstance(o, Variable):
                # `o` is expected to be a field of a `struct`ure.
                # Else, `RPCBufferVisitor` is used incorrectly.
                res = OpSDeref(res, o.name)
        return res


class RPCBufferResetter(RPCBufferVisitor):

    def on_visit(self):
        cur = self.cur

        if cur is RPCBuffer or cur is RPCString:
            buf_lval = self.deref_root_val
            fiter = iter(cur.fields)
            self._ops.extend((
                # Note, field names are different in RPCBuffer/RPCString.
                OpAssign(OpSDeref(buf_lval, next(fiter)), 0),
                OpAssign(OpSDeref(buf_lval, next(fiter)), NULL),
            ))
            raise SkipVisiting


class RPCExtraRetSizeCounter(RPCBufferVisitor):

    def __init__(self, size_lval, *a, **kw):
        super(RPCExtraRetSizeCounter, self).__init__(*a, **kw)
        self._size_lval = size_lval

    def on_visit(self):
        cur = self.cur

        if cur is RPCBuffer or cur is RPCString:
            buf = self.deref_root_val
            fiter = iter(cur.fields)

            inc_val = OpSDeref(buf, next(fiter))
            # if cur is RPCString:
            #     inc_val = OpAdd(inc_val, 1) # zero string terminator

            data_val = OpSDeref(buf, next(fiter))

            self._ops.append(
                BranchIf(OpNEq(data_val, NULL)) (
                    OpCombAssign(self._size_lval, inc_val, "+")
                )
            )

            raise SkipVisiting


# a method @decorator
class rpc(object):

    def __init__(self, return_type, *arguments_types):
        self.return_type = return_type
        self.arguments_types = arguments_types

    def __call__(self, method):
        info =  RPCInfo(method, self.return_type, self.arguments_types)

        @wraps(method)
        def rpc_wrapper(self, *a, **kw):
            argvals = info.serialize_args(a, kw)
            # Original method may check values and raise an excption
            method(self, *argvals)
            # Note, isinstance(self, RPCFrontEnd)
            return self.rpc(info, argvals)

        rpc_wrapper.rpc_info = info

        return rpc_wrapper


class RPCInfo(object):

    def __init__(self, method, return_type, arguments_types):
        args, __, __, defaults = getargspec(method)
        args = args[1:] # strip `self` out

        if len(args) < len(arguments_types):
            raise ValueError("Unused arguments type(s): "
                + ", ".join(arguments_types[len(args):])
            )
        elif len(arguments_types) < len(args):
            raise ValueError("No type(s) for last argument(s): "
                + ", ".join(args[len(arguments_types):])
            )

        self.name = method.__name__
        self.method = method

        with get_stc():
            if return_type is not None and not isinstance(return_type, Type):
                return_type = Type[return_type]

            types = tuple((t if isinstance(t, Type) else Type[t])
                for t in arguments_types
            )

        self.return_type = return_type
        self.args = OrderedDict(zip(args, types))

        if defaults is None:
            self.defaults = dict()
        else:
            pos_args_count = len(args) - len(defaults)
            kw_args = args[pos_args_count:]
            self.defaults = dict(zip(kw_args, defaults))

        # In the generated RPC protocol calls are numbered according to its
        # relative file positions. So, new methods may be appended below
        # keeping conptibility with earlier implementations.
        code = method.__code__
        self.sort_key = (code.co_filename, code.co_firstlineno)

    def __lt__(self, other):
        return self.sort_key < other.sort_key

    def handle_args(self, a, kw):
        argvals = self.defaults.copy()
        argvals.update(kw)
        argvals.update(zip(self.args, a))
        return argvals

    def serialize_args(self, a, kw):
        argvals = self.handle_args(a, kw)
        return tuple(argvals[a] for a in self.args)

    def gen_impl_decl(self,
        backend_name = "be",
        context_name = "ctx",
        return_name = "ret",
        name_prefix = ""
    ):
        args = [
            RPCBackEnd(backend_name),
            rpc_ptr_t(context_name),
        ]
        if self.return_type is not None:
            args.append(Pointer(self.return_type)(return_name))

        for a, t in self.args.items():
            if isinstance(t, Structure):
                t = Pointer(t)
            args.append(t(a))

        return Function(
            name = name_prefix + self.name,
            ret_type = RPCError,
            args = args,
        )

    def gen_args_packer(self, byte_order = "="):
        if not self.args:
            def packer(*__):
                return b""
            return packer

        fmt, flattener_code = gen_packer_py(self.args.values(), "args",
            count()
        )

        s = Struct(byte_order + fmt)

        args_flattener_code = []
        line = args_flattener_code.append

        line("def flattener(args, tail):")
        for l in flattener_code:
            line(" " + l)

        code = "\n".join(args_flattener_code)

        ns = {
            "text_type" : text_type
        }
        exec(code, ns)

        flattener = ns["flattener"]

        def packer(*args):
            tail = []
            return s.pack(*flattener(args, tail)) + b"".join(tail)

        return packer

    def gen_retval_unpacker(self, byte_order = "="):
        return_type = self.return_type

        if return_type is None:
            return lambda __ : None

        ret_unflattener_code = []
        line = ret_unflattener_code.append

        fmt, tree_code, l_vals, post_unflatten_code = gen_unpacker_py(
            (("retval", return_type),),
            "ret",
            count()
        )

        s = Struct(byte_order + fmt)

        if isinstance(return_type, Structure):
            line("def unflattener(values, tail):")
            line(" ret = {}")
            for l in tree_code:
                line(" " + l)

            line(" (" + ", ".join(l_vals) + ",) = values")

            for l in post_unflatten_code:
                line(" " + l)

            line(" return ret['retval']")

            code = "\n".join(ret_unflattener_code)

            ns = {}
            exec(code, ns)

            unflattener = ns["unflattener"]
            ssize = s.size

            def unpacker(raw_data):
                return unflattener(
                    s.unpack(raw_data[:ssize]),
                    raw_data[ssize:]
                )
        else:
            def unpacker(raw_data):
                return s.unpack(raw_data)[0]

        return unpacker

    def iter_handler_ops(self, impl, err, be, ctx, pptr, response,
        response_size
    ):
        unpackers = {}
        packers = {}
        impl_args = [be, ctx]

        ret_type = self.return_type

        if ret_type is not None:
            ret_arg = ret_type("ret")
            yield Declare(ret_arg)
            impl_args.append(OpAddr(ret_arg))

            for n in RPCBufferResetter(ret_arg, ret_type).iter_ops():
                yield n

        # unpack arguments
        args_lvals_and_types = []
        for arg, t in self.args.items():
            arg_var = t(arg)
            if isinstance(t, Structure):
                impl_args.append(OpAddr(arg_var))
            else:
                impl_args.append(arg_var)
            yield Declare(arg_var)
            args_lvals_and_types.append((arg_var, t))

        for node in iter_gen_unpacker_c(args_lvals_and_types, pptr,
            unpackers
        ):
            yield node

        # handle `RSPBuffer`s & `RPCString`s
        queue = list(args_lvals_and_types)
        while queue:
            lval, t = queue.pop(0)

            if isinstance(t, Structure):
                if t is RPCBuffer:
                    yield OpAssign(OpSDeref(lval, "data"), OpDeref(pptr))
                    yield OpCombAssign(
                        OpDeref(pptr),
                        OpSDeref(lval, "size"),
                        "+"
                    )
                elif t is RPCString:
                    yield OpAssign(OpSDeref(lval, "data"), OpDeref(pptr))
                    yield OpCombAssign(
                        OpDeref(pptr),
                        OpAdd(OpSDeref(lval, "length"), 1),
                        "+"
                    )
                else:
                    queue.extend(
                        (OpSDeref(lval, n), v.type)
                            for (n, v) in t.fields.items()
                    )

        yield OpAssign(err, Call(impl, *impl_args))

        if ret_type is not None:
            yield BranchIf(OpNEq(err, Type["RPC_ERR_NO"]))(
                Break()
            )

            total_buffers = RPCBufferCounter(ret_type).total

            if total_buffers:
                # Note, OpSizeOf(ret_type) is likely greater than amount
                # of really needed bytes because of compiller assumes that
                # returned `struct`ure fields are aligned in memory resulting
                # in padding between them.
                # And `response_size` includes the padding.
                # However, returned data is tightly packed by the generated
                # code. As a result, there is an unused zero tail in message.
                # TODO: evaluate response size more accurately

                response_size_val = response_size.type.type("total_size")
                yield Declare(
                    OpDeclareAssign(response_size_val,
                        # Each RPCBuffer/RPCString `struct`ure has a data
                        # pointer field. That pointer (its local value) is
                        # not transmitted and must not be accounted in
                        # response size.
                        OpSub(
                            OpSizeOf(ret_type),
                            OpMul(total_buffers,
                                OpSizeOf(RPCBuffer.fields["data"].type)
                            )
                        )
                    )
                )

                for n in RPCExtraRetSizeCounter(
                    response_size_val, ret_arg, ret_type
                ):
                    yield n
            else:
                response_size_val = OpSizeOf(ret_type)

            # allocate memory for response
            yield OpAssign(err,
                Call(rpc_backend_alloc_response, be,
                    response_size_val,
                    response
                )
            )
            yield BranchIf(OpNEq(err, Type["RPC_ERR_NO"]))(
                Break()
            )
            yield OpAssign(
                OpDeref(response_size),
                response_size_val
            )

            # pack returned value into response
            r = response.type.type("r")
            yield Declare(OpDeclareAssign(r, OpDeref(response)))
            rptr = pptr.type("rp")
            yield Declare(OpDeclareAssign(rptr, OpAddr(r)))
            for n in iter_gen_packer_c([(ret_arg, ret_type)], rptr, packers):
                yield n#ode

            # handle `RSPBuffer`s & `RPCString`s
            queue = [(ret_arg, ret_type)]
            while queue:
                rval, t = queue.pop(0)

                if isinstance(t, Structure):
                    fiter = iter(t.fields)
                    size_name = next(fiter)
                    data_name = next(fiter)

                    if t is RPCBuffer or t is RPCString:
                        yield BranchIf(OpNEq(OpSDeref(rval, data_name), NULL))(
                            Call(memcpy,
                                OpDeref(rptr),
                                OpSDeref(rval, data_name),
                                OpSDeref(rval, size_name)
                            ),
                            OpCombAssign(
                                OpDeref(rptr),
                                OpSDeref(rval, size_name),
                                "+"
                            ),
                        )
                    else:
                        queue.extend(
                            (OpSDeref(rval, n), v.type)
                                for (n, v) in t.fields.items()
                        )


# Standard C types (char, int, long) have host dependent sizes.
# They are not used by base implementation.
# But one can add them to `simple_type_fmts` mapping if needed.
simple_type_fmts = {
    "int8_t" : "b",
    "uint8_t" : "B",
    "bool" : "?",
    "int16_t" : "h",
    "uint16_t" : "H",
    "int32_t" : "i",
    "uint32_t" : "I",
    "int64_t" : "q",
    "uint64_t" : "Q",
    "float" : "f",
    "double" : "d",
}


def gen_packer_py(types_iter, obj_name, counter):
    fmt = ""

    flattener_code = []
    line = flattener_code.append

    i_name = "i" + str(next(counter))
    line(i_name + " = iter(" + obj_name + ")")

    for t in types_iter:
        if isinstance(t, Structure):
            s_name = "s" + str(next(counter))
            line(s_name + " = next(" + i_name + ")")
            s_fmt, s_flattener_code = gen_structure_packer_py(t, s_name,
                counter
            )
            fmt += s_fmt

            flattener_code.extend(s_flattener_code)
        else:
            try:
                f = simple_type_fmts[t.name]
            except KeyError:
                raise ValueError("Don't know how to pack type " + t.name)

            fmt += f
            line("yield next(" + i_name + ")")

    return fmt, flattener_code


def iter_gen_unpacker_c(lvals_types_iter, pptr, unpackers):
    for lval, t in lvals_types_iter:
        if isinstance(t, Structure):
            if t is RPCBuffer or t is RPCString:
                uint16_t = Type["uint16_t"]
                size_var = OpSDeref(lval, next(iter(t.fields)))
                yield OpAssign(
                    size_var,
                    OpDeref(OpCast(Pointer(uint16_t), OpDeref(pptr)))
                )
                yield OpCombAssign(OpDeref(pptr), OpSizeOf(uint16_t), "+")
            else: # generic structure
                if t in unpackers:
                    t_unpacker = unpackers[t]
                else:
                    t_unpacker = gen_struct_handler_c(t, "unpack_", unpackers,
                        iter_gen_unpacker_c
                    )
                    unpackers[t] = t_unpacker

                yield Call(t_unpacker, OpAddr(lval), pptr)
        else:
            yield OpAssign(lval, OpDeref(OpCast(Pointer(t), OpDeref(pptr))))
            yield OpCombAssign(OpDeref(pptr), OpSizeOf(t), "+")


def iter_gen_packer_c(rvals_types_iter, pptr, packers):
    for rval, t in rvals_types_iter:
        if isinstance(t, Structure):
            if t is RPCBuffer or t is RPCString:
                fiter = iter(t.fields)
                size_name = next(fiter)
                data_name = next(fiter)

                size_type = t.fields[size_name].type

                yield BranchIf(OpNEq(OpSDeref(rval, data_name), NULL))(
                    OpAssign(
                        OpDeref(OpCast(Pointer(size_type), OpDeref(pptr))),
                        OpSDeref(rval, size_name)
                    ),
                    BranchElse()(
                        OpAssign(
                            OpDeref(OpCast(Pointer(size_type), OpDeref(pptr))),
                            0
                        ),
                    )
                )
                yield OpCombAssign(OpDeref(pptr), OpSizeOf(size_type), "+")
            else:
                if t in packers:
                    t_packer = packers[t]
                else:
                    t_packer = gen_struct_handler_c(t, "pack_", packers,
                        iter_gen_packer_c
                    )
                    packers[t] = t_packer
                yield Call(t_packer, OpAddr(rval), pptr)
        else:
            yield OpAssign(OpDeref(OpCast(Pointer(t), OpDeref(pptr))), rval)
            yield OpCombAssign(OpDeref(pptr), OpSizeOf(t), "+")


def gen_struct_handler_c(t, name_prefix, handlers, recursion):
    target = Pointer(t)("s")
    pptr = Pointer(Pointer(Type["uint8_t"]))("pp")

    body = BodyTree()

    def iter_fields_lvals_and_types():
        for n, f in t.fields.items():
            yield OpSDeref(target, n), f.type

    body(*recursion(iter_fields_lvals_and_types(), pptr, handlers))

    func = Function(
        name_prefix + t.name,
        args = [
            target,
            pptr
        ],
        body = body
    )

    return func


def gen_buffer_packer_py(t, obj_name):
    flattener_code = []
    line = flattener_code.append

    # auto encode utf-8 strings
    line("if isinstance(" + obj_name + ", text_type):")
    line(" " + obj_name + "_ = " + obj_name + ".encode('utf-8')")
    line("else:")
    line(" " + obj_name + "_ = bytes(" + obj_name + ")")

    line("yield len(" + obj_name + "_)")

    if t is RPCString:
        line(obj_name + "_ += b'\\x00'")

    line("tail.append(" + obj_name + "_)")

    return "H", flattener_code


def gen_structure_packer_py(s, obj_name, counter):
    if s is RPCBuffer or s is RPCString:
        return gen_buffer_packer_py(s, obj_name)
    # else:
    #     generic structure

    fmt = ""
    flattener_code = []
    line = flattener_code.append
    pfx = obj_name + "."

    for f in s.fields.values():
        n = f.name
        t = f.type

        if isinstance(t, Structure):
            s_name = "s" + str(next(counter))
            line(s_name + " = " + pfx + n)

            s_fmt, s_flattener_code = gen_structure_packer_py(t, s_name,
                counter
            )
            fmt += s_fmt

            flattener_code.extend(s_flattener_code)
        else:
            if not t.is_named:
                raise ValueError("Don't know how to pack type " + str(t))
            try:
                f = simple_type_fmts[t.name]
            except KeyError:
                raise ValueError("Don't know how to pack type " + t.name)

            fmt += f
            line("yield " + pfx + n)

    return fmt, flattener_code


def gen_unpacker_py(items, dict_name, counter):
    fmt = ""
    l_vals = []
    tree_code = []
    post_unflatten_code = []

    for n, t in items:
        item_expr = dict_name + "['" + n + "']"

        if t is RPCBuffer or t is RPCString:
            size_field = next(iter(t.fields.values())) # it's first
            fmt += simple_type_fmts[size_field.type.name]
            l_vals.append(item_expr)

            # `RPCBuffer` is returned as `bytes` (i.e. raw data)
            # `RPCString` is returned as utf-8 containing type
            #  (Eg.: Py2: `unicode`, Py3: `str`).
            if t is RPCString:
                decode_sfx = ".decode('utf-8')"
            else:
                decode_sfx = ""

            post_unflatten_code.extend((
                "_buf_size = " + item_expr,
                item_expr + " = tail[:_buf_size]" + decode_sfx,
                "tail = tail[_buf_size:]",
                "del _buf_size",
            ))
        elif isinstance(t, Structure):
            inner_dict_name = "d" + str(next(counter))
            tree_code.append(item_expr + " = " + inner_dict_name + " = {}")
            (
                s_fmt, s_tree_code, s_l_vals, s_post_unflatten_code
            ) = gen_unpacker_py(
                ((f.name, f.type) for f in t.fields.values()),
                inner_dict_name, counter
            )
            fmt += s_fmt
            l_vals.extend(s_l_vals)
            tree_code.extend(s_tree_code)
            post_unflatten_code.extend(s_post_unflatten_code)
        else:
            try:
                f = simple_type_fmts[t.name]
            except KeyError:
                raise ValueError("Don't know how to pack type " + t.name)

            fmt += f
            l_vals.append(item_expr)

    return fmt, tree_code, l_vals, post_unflatten_code


def iter_rpc(cls):
    yelded = set() # overriding
    remember = yelded.add

    for c in getmro(cls):
        for n, v in c.__dict__.items():
            if hasattr(v, "rpc_info"):
                info = v.rpc_info

                if n in yelded:
                    continue

                yield c, n, info
                remember(n)


def gen_rpc_impl_header(cls, path, **hdr_kw):
    hdr = Header(path, **hdr_kw)

    fill_rpc_impl_header(cls, hdr)

    return hdr


def fill_rpc_impl_header(cls, hdr, **decl_gen_kw):
    name_prefix = decl_gen_kw.pop("name_prefix", "")
    for c, __, info in sorted(tuple(iter_rpc(cls))):
        f = info.gen_impl_decl(
            name_prefix = name_prefix + c.__name__ + "_",
            **decl_gen_kw
        )
        hdr.add_type(f)


def swap(i):
    for a, b in i:
        yield b, a


def fitting_fmt(max_val):
    if max_val < 0x100:
        return "B"
    elif max_val < 0x10000:
        return  "H"
    elif max_val < 0x100000000:
        return "I"
    elif max_val < 0x10000000000000000:
        return "Q"
    else:
        return None


def fitting_c_type(max_val):
    if max_val < 0x100:
        return Type["uint8_t"]
    elif max_val < 0x10000:
        return  Type["uint16_t"]
    elif max_val < 0x100000000:
        return Type["uint32_t"]
    elif max_val < 0x10000000000000000:
        return Type["uint64_t"]
    else:
        return None


class RPCProtocol(object):

    def __init__(self, frontend_class, byte_order = "="):
        self.fe = frontend_class
        self.byte_order = byte_order

        self.infos = infos = []
        for __, __, info in iter_rpc(frontend_class):
            insort(infos, info)

        i2id = dict(swap(enumerate(infos)))

        i2ap = dict(
            (i, i.gen_args_packer(byte_order = byte_order))
                for i in infos
        )
        i2ru = dict(
            (i, i.gen_retval_unpacker(byte_order = byte_order))
                for i in infos
        )

        self.info2call = dict(
            (i, (i2id[i], i2ap[i], i2ru[i])) for i in infos
        )

        self.id_count = id_count = len(i2id)
        id_fmt = fitting_fmt(id_count)
        if id_fmt is None:
            raise Exception("Too many calls: " + str(id_fmt))

        self.id_packer = Struct(id_fmt).pack

        msg_packer = Struct(byte_order + "I").pack

        def pack_message(msg):
            return msg_packer(len(msg)) + msg

        self.pack_message = pack_message

    def __call__(self, conn, info, argvals):
        id_, ap, ru = self.info2call[info]

        raw_msg = self.id_packer(id_) + ap(*argvals)

        raw_res = conn(raw_msg)

        res_code = raw_res[:1]
        res_payload = raw_res[1:]

        if res_code == b"\x00":
            return ru(res_payload)
        else:
            raise Exception(res_payload)

    def iter_messages(self, read):
        buf = b""

        len_unpack = Struct(self.byte_order + "I").unpack

        while True:
            if len(buf) < 4:
                buf += read(4 - len(buf))
                continue

            msg_len = len_unpack(buf[:4])[0]
            buf = buf[4:]

            while len(buf) < msg_len:
                buf += read(msg_len - len(buf))

            msg = buf[:msg_len]
            buf = buf[msg_len:]

            yield msg

    def gen_be_handle_message(self,
        decl_name = "rpc_backend_handle_message",
        impl_name_prefix = "",
    ):
        fe = self.fe
        impl_prefix = impl_name_prefix + fe.__name__ + "_"

        uint8_t = Type["uint8_t"]

        decl = Type[decl_name]
        be = decl["be"]
        ctx = decl["ctx"]
        msg = decl["msg"]
        response = decl["response"]
        response_size = decl["response_size"]

        call_id_t = fitting_c_type(self.id_count)

        call_id = call_id_t("call_id")
        err = RPCError("err")
        p = Pointer(uint8_t)("p")
        pptr = Pointer(p.type)("pp")

        body = BodyTree()
        body(Declare(OpDeclareAssign(err, Type["RPC_ERR_NO"])))

        body(OpAssign(p, OpCast(Pointer(uint8_t), msg)))
        body(Declare(OpDeclareAssign(pptr, OpAddr(p))))

        if self.byte_order != "=":
            # TODO: swap bytes of call_id if needed
            raise NotImplementedError("Only native byte order now")

        body(OpAssign(call_id, OpDeref(OpCast(Pointer(call_id_t), p))))

        body(OpCombAssign(p, OpSizeOf(call_id_t), "+"))

        # TODO: implement message size verification
        # uint32_t = Type["uint32_t"]
        # msg_size = decl["msg_size"]
        # args_size = uint32_t("args_size")
        # body(OpDeclareAssign(args_size, OpSub(msg_size, call_id_size)))

        switch = BranchSwitch(call_id)
        body(switch)

        for cid, info in enumerate(self.infos):
            case = SwitchCase(cid)
            switch(case)

            case(Comment(info.name))
            case(*info.iter_handler_ops(
                Type[impl_prefix + info.name],
                err, be, ctx, pptr, response, response_size
            ))

        default = SwitchCaseDefault()
        switch(default)

        default(OpAssign(err, Type["RPC_ERR_UNIMPL_CALL"]))

        body(Return(err))

        return decl.gen_definition(body)

    def gen_handler_module(self, path, **src_kw):
        mod = Source(path, **src_kw)

        mod(self.gen_be_handle_message())

        return mod

    def gen_impl_hdr(self, path, **hdr_kw):
        return gen_rpc_impl_header(self.fe, path, **hdr_kw)

    def gen_impl_mod(self, path, **src_kw):
        impl_prefix = self.fe.__name__ + "_"

        mod = Source(path, **src_kw)

        body = BodyTree()
        body(Return(Type["RPC_ERR_NO"]))

        for info in self.infos:
            mod(Type[impl_prefix + info.name].gen_definition(body = body))

        return mod

    def iter_gen_sources(self,
        impl_hdr_path = "impl.h",
        impl_mod_path = "impl.boilerplate.c",
        be_mod_path = "handler.c",
    ):
        yield self.gen_impl_hdr(impl_hdr_path, protection_prefix = "")
        yield self.gen_handler_module(be_mod_path, locked_inclusions = False)

        # Some modules are generated optionally.
        if impl_mod_path is not None:
            yield self.gen_impl_mod(impl_mod_path, locked_inclusions = False)


class RPCStreamConnection(object):

    def __init__(self, to_remote, from_remote):
        self.to_remote = to_remote
        self.from_remote = from_remote

        self.read = from_remote.read
        self.write = to_remote.write


class RPCFrontEnd(object):

    def __init__(self):
        self._protocol = RPCProtocol(type(self))

    @property
    def connection(self):
        return self._connection

    @connection.setter
    def connection(self, connection):
        self._connection = connection

        p = self._protocol
        message_iterator = p.iter_messages(connection.read)
        pack_message = p.pack_message
        write = connection.write

        def conn(msg):
            write(pack_message(msg))
            return next(message_iterator)

        def rpc(info, argvals):
            return p(conn, info, argvals)

        self.rpc = rpc
