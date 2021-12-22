from rpc import (
    get_stc,
    rpc,
    RPCFrontEnd,
    RPCStreamConnection,
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
from os.path import (
    abspath,
    dirname,
    join,
)
from SCons.Script.Main import (
    _build_targets,
    _set_debug_values,
)
from SCons.Script.SConsOptions import (
    Parser,
    SConsValues,
)
from SCons.Script.SConscript import (
    SConsEnvironment,
)
from subprocess import (
    Popen,
    PIPE,
)



def main():
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

    RPCBuffer = Type["RPCBuffer"]
    RPCString = Type["RPCString"]
    BufCmpTask = Structure("BufCmpTask",
        RPCBuffer("a"),
        RPCBuffer("b")
    )
    VersionInfo = Structure("VersionInfo",
        RPCBuffer("version_string"),
        Type["uint32_t"]("version_code"),
    )


    class RPCBufferFE(object):

        def __init__(self, a, b):
            self.a = a
            self.b = b

        def __str__(self):
            return type(self).__name__ + "(%s, %s)" % (self.a, self.b)

    class TestFrontEnd(RPCFrontEnd):

        @rpc(None, "int32_t")
        def m1(self, a):
            print("TestFrontEnd.m1", a)

        @rpc(None, "int32_t")
        def m2(self, a = 1):
            print("TestFrontEnd.m2", a)

        @rpc(None, "int32_t", "int32_t", "int32_t")
        def m3(self, a, b, c = 3):
            print("TestFrontEnd.m3", a, b, c)

        @rpc("Point3i", Point3i, "Point3i")
        def vadd(self, a, b):
            print("TestFrontEnd.vadd", a, b)

        @rpc(None)
        def stop(self):
            print("TestFrontEnd.stop")

        @rpc(None, "RPCString")
        def p(self, s):
            print("p", s)

        @rpc("int8_t", "RPCString", "RPCString")
        def strcmp(self, a, b):
            print("strcmp", a, b)

        @rpc("int8_t", BufCmpTask)
        def bufcmp(self, t):
            print("bufcmp", t)

        @rpc(RPCString)
        def version_string(self):
            print("TestFrontEnd.version_string")

        @rpc(VersionInfo)
        def version_info(self):
            print("TestFrontEnd.version_info")

    # not correct, just for unpacker testing
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

    print(fe.vadd(p0, p1))

    packer = fe.vadd.rpc_info.gen_args_packer()

    raw = packer(p0, p1)
    print(raw)

    unpacker = fe.vadd.rpc_info.gen_retval_unpacker()

    p = unpacker(raw2)
    print(p)

    script_dir = dirname(abspath(__file__))
    rpc_probe_dir = join(script_dir, "rpc_probe")

    files = [
        join(rpc_probe_dir, "impl.c"),
        join(rpc_probe_dir, "rpc_probe.c")
    ]

    for s in protocol.iter_gen_sources():
        f = s.generate()

        string_buf = StringIO()
        f.generate(string_buf)

        code = string_buf.getvalue()

        f_name = join(rpc_probe_dir, s.path)

        with open(f_name, "w") as io:
            io.write(code)

        if "boilerplate" not in f_name and not f.is_header:
            files.append(f_name)

    prog_name = join(rpc_probe_dir, "rpc_probe.exe")

    rpc_include = join(dirname(script_dir), "rpc")

    files.append(join(rpc_include, "be.c"))
    files.append(join(rpc_include, "server.c"))

    env = SConsEnvironment(CFLAGS = " ".join((
        "-I" + rpc_include,
        "-D" + "RPC_DEBUG=1",
    )))
    env.Default(env.Program(prog_name, files))

    parser = Parser([])
    values = SConsValues(parser.get_default_values())
    parser.parse_args([], values)
    options = parser.values
    _set_debug_values(options)
    _build_targets(None, options, [prog_name], None)

    p = Popen([prog_name], stdin = PIPE, stdout = PIPE, bufsize = 0)
    conn = RPCStreamConnection(p.stdin, p.stdout)
    fe.connection = conn

    print(fe.version_string())
    print(fe.version_info())
    print(fe.vadd(p0, p1))
    print(fe.m1(2))
    print(fe.m2())
    print(fe.m3(4, 5))
    print(fe.p("Test p"))
    print(fe.strcmp("aaa", "bbb"))
    print(fe.strcmp("bbb", "aaa"))
    print(fe.strcmp(b"cccc", u"cccc"))
    print(fe.bufcmp(RPCBufferFE(a = b"aaa", b = b"bbb")))
    print(fe.bufcmp(RPCBufferFE(a = b"aaa", b = b"aaaa")))
    print(fe.stop())

if __name__ == "__main__":
    exit(main() or 0)
