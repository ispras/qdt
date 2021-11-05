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
    BranchSwitch,
    Comment,
    SwitchCase,
    SwitchCaseDefault,
    Declare,
    Enumeration,
    Function,
    Header,
    OpAssign,
    OpCast,
    OpCombAssign,
    OpDeclareAssign,
    OpDeref,
    OpSub,
    Pointer,
    Return,
    Source,
    SourceTreeContainer,
    Structure,
    Type,
)
from struct import (
    Struct,
)
from bisect import (
    insort,
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

    global void
    void = Type["void"]

    # TODO: parse those from rpc.h or generate rpc.h entirely
    global RPCError
    RPCError = Enumeration([
            "RPC_ERR_NO",
            "RPC_ERR_READ",
            "RPC_ERR_WRITE",
            "RPC_ERR_ALLOC",
            "RPC_ERR_UNIMPL_CALL",
            "RPC_ERR_COUNT"
        ],
        typedef_name = "RPCError"
    )

    global rpc_ptr_t
    rpc_ptr_t = Pointer(void, name = "rpc_ptr_t")

    global RPCBackEnd
    RPCBackEnd = Pointer(void, name = "RPCBackEnd")


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
        return_name = "ret",
        name_prefix = ""
    ):
        args = [
            RPCBackEnd(backend_name),
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

    def gen_args_packer(self, byte_order = "@"):
        fmt, flattener_code = gen_packer(self.args.values(), "args", count())

        s = Struct(byte_order + fmt)

        args_flattener_code = []
        line = args_flattener_code.append

        line("def flattener(args):")
        for l in flattener_code:
            line(" " + l)

        code = "\n".join(args_flattener_code)

        ns = {}
        exec(code, ns)

        flattener = ns["flattener"]

        def packer(*args):
            return s.pack(*flattener(args))

        return packer

    def gen_retval_unpacker(self, byte_order = "@"):
        if self.return_type is None:
            return lambda __ : None

        fmt, tree_code, l_vals = gen_unpacker(
            (("retval", self.return_type),),
            "ret",
            count()
        )

        s = Struct(byte_order + fmt)

        ret_unflattener_code = []
        line = ret_unflattener_code.append

        line("def unflattener(values):")
        line(" ret = {}")
        for l in tree_code:
            line(" " + l)

        line(" (" + ", ".join(l_vals) + ") = values")
        line(" return ret['retval']")

        code = "\n".join(ret_unflattener_code)

        ns = {}
        exec(code, ns)

        unflattener = ns["unflattener"]

        def unpacker(raw_data):
            return unflattener(s.unpack(raw_data))

        return unpacker

    def iter_handler_ops(self, err, be, p, args_size, response, response_size):
        return
        yield


# Standard C types (char, int, long) have host dependent sizes.
# They are not used by base implementation.
# By one can add them to `simple_type_fmts` mapping if needed.
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


def gen_packer(types_iter, obj_name, counter):
    fmt = ""

    flattener_code = []
    line = flattener_code.append

    i_name = "i" + str(next(counter))
    line(i_name + " = iter(" + obj_name + ")")

    for t in types_iter:
        if isinstance(t, Structure):
            s_name = "s" + str(next(counter))
            line(s_name + " = next(" + i_name + ")")
            s_fmt, s_flattener_code = gen_structure_packer(t, s_name, counter)
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


def gen_structure_packer(s, obj_name, counter):
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

            s_fmt, s_flattener_code = gen_structure_packer(t, s_name, counter)
            fmt += s_fmt

            flattener_code.extend(s_flattener_code)
        else:
            try:
                f = simple_type_fmts[t.name]
            except KeyError:
                raise ValueError("Don't know how to pack type " + t.name)

            fmt += f
            line("yield " + pfx + n)

    return fmt, flattener_code


def gen_unpacker(items, dict_name, counter):
    fmt = ""
    l_vals = []
    l_val = l_vals.append

    tree_code = []
    line = tree_code.append

    for n, t in items:
        item_expr = dict_name + "['" + n + "']"

        if isinstance(t, Structure):
            inner_dict_name = "d" + str(next(counter))
            line(item_expr + " = " + inner_dict_name + " = {}")
            s_fmt, s_tree_code, s_l_vals = gen_unpacker(
                ((f.name, f.type) for f in t.fields.values()),
                inner_dict_name, counter
            )
            fmt += s_fmt
            l_vals.extend(s_l_vals)
            tree_code.extend(s_tree_code)
        else:
            try:
                f = simple_type_fmts[t.name]
            except KeyError:
                raise ValueError("Don't know how to pack type " + t.name)

            fmt += f
            l_val(item_expr)

    return fmt, tree_code, l_vals


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


def fitting_c_type_size(max_val):
    if max_val < 0x100:
        return 1
    elif max_val < 0x10000:
        return  2
    elif max_val < 0x100000000:
        return 4
    elif max_val < 0x10000000000000000:
        return 8
    else:
        return None


class RPCProtocol(object):

    def __init__(self, frontend_class, byte_order = "@"):
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
        name = "rpc_backend_handle_message",
    ):
        uint32_t = Type["uint32_t"]
        uint8_t = Type["uint8_t"]

        decl = Function(
            name = name,
            ret_type = RPCError,
            args = [
                RPCBackEnd("be"),
                rpc_ptr_t("msg"),
                uint32_t("msg_size"),
                Pointer(rpc_ptr_t)("response"),
                Pointer(uint32_t)("response_size")
            ]
        )

        be = decl["be"]
        msg = decl["msg"]
        msg_size = decl["msg_size"]
        response = decl["response"]
        response_size = decl["response_size"]

        call_id_t = fitting_c_type(self.id_count)
        call_id_size = fitting_c_type_size(self.id_count)

        call_id = call_id_t("call_id")
        err = RPCError("err")
        p = uint8_t("p")

        body = BodyTree()
        body(Declare(call_id))
        body(Declare(OpDeclareAssign(err, Type["RPC_ERR_NO"])))
        body(Declare(p))

        body(OpAssign(p, OpCast(Pointer(uint8_t), msg)))

        if self.byte_order != "@":
            # TODO: swap bytes of call_id if needed
            raise NotImplementedError("Only native byte order now")

        body(OpAssign(call_id, OpDeref(OpCast(Pointer(call_id_t), p))))

        body(OpCombAssign(p, call_id_size, "+"))

        args_size = uint32_t("args_size")
        body(OpDeclareAssign(args_size, OpSub(msg_size, call_id_size)))

        switch = BranchSwitch(call_id)
        body(switch)

        for cid, info in enumerate(self.infos):
            case = SwitchCase(cid)
            switch(case)

            case(Comment(info.name))
            case(*info.iter_handler_ops(
                err, be, p, args_size, response, response_size
            ))

        default = SwitchCaseDefault()
        switch(default)

        default(OpAssign(err, Type["RPC_ERR_UNIMPL_CALL"]))

        body(Return(err))

        return decl.gen_definition(body)

    def gen_be_module(self, path, **src_kw):
        mod = Source(path, **src_kw)

        mod(self.gen_be_handle_message())

        return mod


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
