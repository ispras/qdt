__all__ = [
# Re-usable generic classes.
    "comma_escape"
  , "iter_dict_as_args"
  , "Namespace"
  , "Portspace"

# CLI arguments model.
  , "Parametrizible"
      , "StrParam"
          , "AllocableParameter"
              , "TCPPort"
              , "Chardev"
                  , "TCPChardev"
      , "ParametrizedStr"
          , "QemuAttr"
          , "QemuBoolAttr"
      , "QemuValue"
          , "QemuBoolValue"

    , "QemuOptsList"

  , "Context"
      , "QLaunch"

  , "QemuProcess"
    , "ExampleQemuProcess"
]


from common import (
    CoReturn,
    ProcessCoOperator,
    pypath,
)
from itertools import (
    count,
)
from socket import (
    SOCK_STREAM,
    AF_INET,
    SOL_SOCKET,
    SO_REUSEADDR,
    socket,
)
from sys import (
    exc_info,
)
from traceback import (
    format_exc,
)
# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        find_free_port,
    )


def comma_escape(s):
    ", is an opt separator in Qemu opt list. ,, is , literally."
    parts = s.split(",")
    return ",,".join(parts)


def iter_dict_as_args(d):
    for a, v in d.items():
        if v is None:
            continue
        if v is False:
            yield "-no-" + str(a)
        elif v is True:
            yield "-" + str(a)
        elif isinstance(v, (list, tuple, set)):
            for sub_v in v:
                yield "-" + str(a)
                yield str(sub_v)
        else:
            yield "-" + str(a)
            yield str(v)


class Namespace(set):

    def gen_uniq(self, prefix):
        if prefix in self:
            for i in count():
                name = prefix + str(i)
                if name not in self:
                    break
        else:
            name = prefix

        self.add(name)
        return name


class Portspace(object):

    def __init__(self):
        self.next = 1024

    def get_free_port(self):
        port = find_free_port(start = self.next)
        if port is None:
            raise RuntimeError("No free ports")
        self.next = port + 1
        return port


class Context(object):

    def __init__(self, portspace = None):
        self.allocable = []

        if portspace is None:
            portspace = Portspace()

        self.portspace = portspace

    def allocate(self):
        # Namespace is always local for a context.
        # Portspace is global (local for host OS).

        self.namespace = Namespace()

        for a in self.allocable:
            a.allocate()

        del self.namespace


class Parametrizible(object):

    def __radd__(self, left):
        return ParametrizedStr(left, self)

    def __add__(self, right):
        return ParametrizedStr(self, right)


class StrParam(Parametrizible):

    def __init__(self, value = None, **kw):
        super(StrParam, self).__init__(**kw)
        self.value = value

    def __str__(self):
        v = self.value
        return "[not-set]" if v is None else str(v)


class ParametrizedStr(Parametrizible):

    def __init__(self, *parts, **kw):
        super(ParametrizedStr, self).__init__(**kw)
        self.parts = parts

    def __str__(self):
        return "".join(map(str, self.parts))


class AllocableParameter(StrParam):

    def __init__(self, ctx, *a, **kw):
        super(AllocableParameter, self).__init__(*a, **kw)
        ctx.allocable.append(self)
        self.ctx = ctx

    def allocate(self):
        raise NotImplementedError("Never use just " + type(self).__name__)


class QemuValue(Parametrizible):

    def __init__(self, obj, attr, **kw):
        super(QemuValue, self).__init__(**kw)
        self.obj = obj
        self.attr = attr

    def __str__(self):
        return str(getattr(self.obj, self.attr))


class QemuBoolValue(QemuValue):

    def __str__(self):
        return "on" if getattr(self.obj, self.attr) else "off"


class QemuAttr(ParametrizedStr):

    def __init__(self, obj, q_attr, obj_attr = None):
        if obj_attr is None:
            obj_attr = q_attr

        super(QemuAttr, self).__init__(
            q_attr, "=", QemuValue(obj, obj_attr)
        )


class QemuBoolAttr(ParametrizedStr):

    def __init__(self, obj, q_attr, obj_attr = None, **kw):
        if obj_attr is None:
            obj_attr = q_attr

        super(QemuBoolAttr, self).__init__(
            q_attr, "=", QemuBoolValue(obj, obj_attr),
            **kw
        )


class QemuOptsList(object):

    def __init__(self, *opts):
        self.opts = opts

    def __str__(self):
        return ",".join(comma_escape(str(opt)) for opt in self.opts)

    def __add__(self, right):
        if isinstance(right, QemuOptsList):
            right = right.opts

        return QemuOptsList(*self.opts, *right)

    def __radd__(self, left):
        if isinstance(left, QemuOptsList):
            left = left.opts

        return QemuOptsList(*left, *self.opts)


class TCPPort(AllocableParameter):

    def __init__(self, ctx, server = False, **kw):
        super(TCPPort, self).__init__(ctx, **kw)
        self.server = server

    def allocate(self):
        if self.server:
            # Qemu will be a server. Alloc a port for it.
            self.value = self.ctx.portspace.get_free_port()
            self.socket = None
        else:
            # Qemu will connect to a port it is given.
            s = socket(family = AF_INET, type = SOCK_STREAM)
            s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            s.bind(("localhost", 0))
            s.listen(1)
            self.value = s.getsockname()[1]
            self.socket = s


class Chardev(AllocableParameter):

    def allocate(self):
        self.value = self.ctx.namespace.gen_uniq("chr")


class TCPChardev(Chardev):

    def __init__(self, ctx,
        port = None,
        wait = False,
        server = False,
        **kw
    ):
        super(TCPChardev, self).__init__(ctx, **kw)

        opts = QemuOptsList(
            "socket",
            QemuAttr(self, "id", obj_attr = "value"),
            QemuAttr(self, "port"),
            QemuBoolAttr(self, "server"),
        )

        if port is None:
            port = TCPPort(ctx, server = server)
        else:
            server = port.server

        if server:
            opts += [QemuBoolAttr(self, "wait")]
        else:
            opts += ["host=localhost"]

        self.port = port
        self.server = server
        self.wait = wait
        self.opts = opts

        self.args = ["-chardev", opts]


class QemuProcess(ProcessCoOperator):
    "API (frontend) to launched Qemu process."

# frontend

    def co_qmp(self, remote):
        """ Handles Qemu Monitor Protocol session.
:param remote:
    A chardevs specific address of QMP connection (e.g. host & port for
    TCP chardevs).

Must be a coroutine.
Never do long running operations here.
`yield` raises exceptions from connection backend (e.g. from socket.recv).
TODO
        """
        yield

    def co_serial(self, idx, remote):
        """ Handles communication through serial port.
:param idx:
    Index of serial.
:param remote:
    A chardevs specific address of serial port connection (e.g. host & port for
    TCP chardevs).

Must be a coroutine.
`yield` returns data received from remote.
`yield` immediately after the data accounting.
Never do long running operations here.
`yield` raises exceptions from connection backend (e.g. from socket.recv).
`yield` can be given data to send (or `None` if nothing to send).
Data must be a r'raw string'.
        """
        yield

# implementation

    def __init__(self, args,
        qmp_chardev = None,
        serial_chardevs = tuple(),
        **kw
    ):
        super(QemuProcess, self).__init__(args, **kw)
        self.qmp_chardev = qmp_chardev
        self.serial_chardevs = serial_chardevs

    def _co_accept(self, chardev):
        server_socket = chardev.port.socket

        # Wait for Qemu to try to connect.
        yield (server_socket, False)
        s_remote = server_socket.accept()

        server_socket.close()

        s_remote[0].setblocking(0)

        raise CoReturn(s_remote)

    def _co_qmp(self):
        chardev = self.qmp_chardev

        s, remote = (yield self._co_accept(chardev))

        recv = s.recv

        # TODO
        # Wait for hello from QMP.

        gen = self.co_qmp(remote)

        try:
            next(gen)
        except StopIteration:
            pass
        else:
            while True:
                try:
                    yield (s, False)
                except GeneratorExit:
                    break
                except:
                    try:
                        gen.throw(*exc_info())
                    except:
                        print(str(gen) + ": exception catch failed:")
                        print(format_exc())
                    break

                chunk = recv(4096)

                if not chunk:
                    break # EOF

                try:
                    gen.send(chunk)
                except StopIteration:
                    break

        s.close()

    def _co_serial(self, idx):
        chardev = self.serial_chardevs[idx]

        s, remote = (yield self._co_accept(chardev))

        send, recv = s.send, s.recv

        gen = self.co_serial(idx, remote)

        try:
            to_send = next(gen)
        except StopIteration:
            pass
        else:
            while True:
                if to_send is not None:
                    send(to_send)

                try:
                    yield (s, False)
                except GeneratorExit:
                    break
                except:
                    try:
                        gen.throw(*exc_info())
                    except:
                        print(str(gen) + ": exception catch failed:")
                        print(format_exc())
                    break

                chunk = recv(4096)

                if not chunk:
                    break # EOF

                try:
                    to_send = gen.send(chunk)
                except StopIteration:
                    break

        s.close()


class QLaunch(Context):
    "Settings for Qemu launching."

    def __init__(self, binary,
        paused = False,
        qmp = False,
        serials = 0,
        extra_args = tuple(),
        **kw
    ):
        super(QLaunch, self).__init__(**kw)

        self.binary = binary
        self.paused = paused
        self.qmp = qmp
        self.serials = serials

        if isinstance(extra_args, dict):
            extra_args_ = list(iter_dict_as_args(extra_args))
        else:
            extra_args_ = list(extra_args)

        self.extra_args = extra_args_

    def launch(self, co_disp, ProcessClass = QemuProcess):
        args = [self.binary]

        if self.paused:
            args.append("-S")

        if self.qmp:
            qmp_chardev = TCPChardev(self)
            args.extend(qmp_chardev.args)
            args.extend([
                "-mon",
                QemuOptsList(
                    "chardev=" + qmp_chardev,
                    "mode=control"
                )
            ])
        else:
            qmp_chardev = None

        serial_chardevs = []

        for __ in range(self.serials):
            chardev = TCPChardev(self)
            serial_chardevs.append(chardev)
            args.extend(chardev.args)

            args.extend(["-serial", "chardev:" + chardev])

        args.extend(self.extra_args)

        self.allocate()

        str_args = list(map(str, args))

        qproc = ProcessClass(str_args,
            qmp_chardev = qmp_chardev,
            serial_chardevs = serial_chardevs,
        )

        enqueue = co_disp.enqueue

        if qmp_chardev is not None:
            enqueue(qproc._co_qmp())

        for idx in range(len(serial_chardevs)):
            enqueue(qproc._co_serial(idx))

        return qproc


class ExampleQemuProcess(QemuProcess):

    def __init__(self, args, *a, **kw):
        print("Starting process: " + str(args))
        super(ExampleQemuProcess, self).__init__(args, *a, **kw)

    def co_qmp(self, remote):
        prefix = "QMP:"

        print(prefix + "DEBUG: connection from " + str(remote))

        while True:
            chunk = (yield)

            print(prefix + chunk.decode("utf-8").rstrip("\r\n"))

    def co_serial(self, idx, remote):
        prefix = "serial%d: " % idx

        print(prefix + "DEBUG: connection from " + str(remote))

        while True:
            chunk = (yield)

            print(prefix + chunk.decode("utf-8").rstrip("\r\n"))

    def co_operate(self):
        while True:
            stdout, stderr = (yield)

            if stdout:
                print("out: " + stdout.decode("utf-8").rstrip("\r\n"))
            if stderr:
                print("err: " + stderr.decode("utf-8").rstrip("\r\n"))

    def finished(self):
        print("finished: " + str(self.wait()))
