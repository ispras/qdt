#!/usr/bin/python

from socket import (
    socket,
    AF_INET,
    SOCK_STREAM
)
from signal import (
    signal,
    SIGINT
)
from time import (
    sleep
)
from argparse import (
    ArgumentParser,
    ArgumentDefaultsHelpFormatter
)
from common import (
    CoDispatcher,
    free_tcp_port
)
from gdb import (
    rsp_unescape,
    rsp_decode,
    assert_ok,
    Features,
    rsp_notification,
    rsp_packet,
    CoRSP
)
from traceback import (
    print_exc
)


def sigint(*a):
    global working
    if not working:
        print("Force exit")
        exit(-1)
    working = False


def co_accept(ss, server):
    while True:
        yield ss, False
        cs, caddr = ss.accept()
        # first line emulates gdbserver
        print("Remote debugging from host %s" % caddr[0])
        print("Remote port %u" % caddr[1])
        CoRSPProxy(server, cs)


class CoRSPVS(CoRSP):
    "Coroutine based Remote Serial Protocol Virtual Server"

    def __init__(self, co_disp, *a, **kw):
        super(CoRSPVS, self).__init__(co_disp, *a, **kw)
        self.co_disp = co_disp

        # server's features when operation as a client
        self.features = feats = Features(
            features = {
                "fork-events" : True,
                "vfork-events" : True,
                "exec-events" : True
            },
            multiprocess = True,
            # xmlRegisters = # some target specific data,
            qRelocInsn = True,
            swbreak = True,
            hwbreak = True,
            vContSupported = True
        )

        self._write("+")
        self.packet(feats.request(), self._stub_features)

    def listen(self, sock):
        self.co_disp.enqueue(co_accept(sock, self))

    def _stub_features(self, data, _):
        self.stub_features = features = Features.parse(data)

        PacketSize = features.get("PacketSize", "")
        if PacketSize:
            try:
                self.packet_size = int(PacketSize, 16)
            except:
                print("Cannot parse PacketSize %s" % PacketSize)
                print_exc()

        if features.get("QStartNoAckMode", False):
            self.packet("QStartNoAckMode", self._start_no_ack_mode)

        if features.get("QNonStop", False):
            self.fetchOK("QNonStop:1")

    def _start_no_ack_mode(self, data, checksum):
        assert_ok(data, checksum)
        self.ack = False


class CoRSPProxy(CoRSP):

    def __init__(self, server, *a, **kw):
        kw.setdefault("verbose", server.verbose)
        super(CoRSPProxy, self).__init__(server.co_disp, *a, **kw)

        self.server = server
        # client's features are same as backing stub with few extensions.
        self.features = Features(server.stub_features,
            QStartNoAckMode = True,
            QNonStop = True
        )

        server.watch_event(self._on_event)
        self.watch_command(self._on_command)

         # Waiting for hello "+" from client
        self.waiting.appendleft(("", 50, None))

    def _on_event(self, server, data, checksum):
        if self._ack:
            self._write(rsp_notification(rsp_unescape(data)))
        else:
            self._write("%" + data + "#" + checksum)

    def _on_command(self, _, data, checksum):
        if data.startswith("qSupported:"):
            self.client_features = Features.parse(data[11:])
            self.packet(self.features.response())
        elif data == "QStartNoAckMode":
            self.ack = False
            self.packet("OK")
        elif data.startswith("QNonStop:"):
            # TODO: data[-1]
            self.packet("OK")
        else:
            server = self.server
            if server._ack:
                server.packet(rsp_unescape(data),
                    callback = self._on_response
                )
            else:
                server.send("$" + data + "#" + checksum,
                    callback = self._on_response
                )

    def _on_response(self, data, checksum):
        if self._ack:
            self.send(rsp_packet(rsp_unescape(data)))
        else:
            self.send("$" + data + "#" + checksum)

#     def _update_features(self, data):
#         new_feats = Features()
#         new_feats.parse(data)
#         self.server.features.stubfeatures.update(new_feats.stubfeatures)
#         feats = self.features
#         feats.stubfeatures = self.server.features.stubfeatures
#         undefined = feats.fit()
#         if undefined:
#             print("Still undefined features: %s" % undefined)
#         self._write(rsp_pack(feats.response()))


def main():
    ap = ArgumentParser(
        description = "GDB RSP proxy",
        formatter_class = ArgumentDefaultsHelpFormatter
    )
    ap.add_argument("-s", "--start",
        type = int,
        metavar = "PORT",
        default = 1234,
        help = "this proxy will start unused port search from this number"
    )
    ap.add_argument("remote",
        nargs = "?",
        default = "127.0.0.1",
        help = "a host with a GDB RSP compatible stub running"
    )
    ap.add_argument("port",
        type = int,
        nargs = "?",
        default = 1234,
        help = "a port listening by the stub"
    )

    args = ap.parse_args()

    disp = CoDispatcher()

    # remote socket
    remote = (args.remote, args.port)
    print("Connecting to %s:%u ..." % remote)
    rs = socket(AF_INET, SOCK_STREAM)
    rs.connect(remote)

    # remote RSP stub
    stub = CoRSPVS(disp, rs,
        verbose = True
    )

    # server socket
    port = free_tcp_port(args.start)
    ss = socket(AF_INET, SOCK_STREAM)
    ss.bind(("", port))
    ss.listen(10)

    print("Listening port %u" % port)

    stub.listen(ss)

    global working
    working = True

    # Ctrl-C support
    signal(SIGINT, sigint)

    while working:
        if not disp.iteration():
            sleep(0.1)

    return 0


if __name__ == "__main__":
    exit(main())
