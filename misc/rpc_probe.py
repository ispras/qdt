from rpc import (
    gen_rpc_impl_header,
    get_stc,
    rpc,
    RPCFrontEnd,
)
from source import (
    Type,
    Structure,
)
from inspect import (
    getargspec,
)
from six.moves import (
    StringIO,
)


def main():
    args = ("a", "b", "c")
    defaults = tuple()

    print(dict(zip(args[-len(defaults):], defaults)))

    defaults = (2, 3)

    print(dict(zip(args[-len(defaults):], defaults)))

    def f(a, b, c, *args):
        pass

    print(getargspec(f))

    with get_stc():
        c_int = Type["int32_t"]
        Point3i = Structure("Point3i", c_int("x"), c_int("y"), c_int("z"))

    class Point3iFE(object):

        def __init__(self, x, y, z):
            self.x = x
            self.y = y
            self.z = z

        def __str__(self):
            return type(self).__name__ + "(%d, %d, %d)" % (
                self.x, self.y, self.z
            )

    class TestFrontEnd(RPCFrontEnd):

        @rpc(None, "int32_t")
        def m1(self, a):
            print(a)

        @rpc(None, "int32_t")
        def m2(self, a = 1):
            print(a)

        @rpc(None, "int32_t", "int32_t", "int32_t")
        def m3(self, a, b, c = 3):
            print(a, b, c)

        @rpc("Point3i", Point3i, "Point3i")
        def cross(self, a, b):
            print(a, b)

    raw2 = b"\xef\xdb\xea\x0d\x0d\xf0\xad\x0b\x01\x02\x03\x04"

    fe = TestFrontEnd()
    protocol = fe._protocol
    pack_message = protocol.pack_message

    class TestConnection(object):

        def write(self, msg):
            call_code = msg[4:5]
            if call_code == b"\x03":
                self.response =  pack_message(b"\x00" + raw2)
            else:
                self.response =  pack_message(b"\x00")

        def read(self, count):
            try:
                return self.response[:count]
            finally:
                self.response = self.response[count:]

    fe.connection = TestConnection()

    fe.m1(2)
    fe.m2()
    fe.m2(2)
    fe.m2(a = 3)
    fe.m3(1, 2)
    fe.m3(1, 2, 4)
    fe.m3(1, 2, c = 5)
    fe.m3(1, b = 6, c = 5)
    fe.m3(a = 7, b = 6, c = 5)

    p0 = Point3iFE(1, 2, 3)
    p1 = Point3iFE(4, 5, 6)

    print(fe.cross(p0, p1))

    hdr = gen_rpc_impl_header(TestFrontEnd, "impl.h")
    hdr_file = hdr.generate()

    string_buf = StringIO()
    hdr_file.generate(string_buf)

    print(string_buf.getvalue())

    packer = fe.cross.rpc_info.gen_args_packer()

    raw = packer(p0, p1)
    print(raw)

    d = dict()
    d2 = dict()
    d["d2"] = d2

    d["v1"], d2["v2"] = 1, 2
    print(d)

    unpacker = fe.cross.rpc_info.gen_retval_unpacker()

    p = unpacker(raw2)
    print(p)

    mod = protocol.gen_be_module("be.c")
    mod_file = mod.generate()

    string_buf = StringIO()
    mod_file.generate(string_buf)

    print(string_buf.getvalue())


if __name__ == "__main__":
    exit(main() or 0)
