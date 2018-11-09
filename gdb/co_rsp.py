__all__ = [
    "CoRSP"
      , "CoRSPClient"
  , "rsp_decode"
  , "assert_ok"
]

from socket import (
    socket,
    AF_INET,
    SOCK_STREAM
)
from .rsp_features import (
    Features
)
from common import (
    notifier,
    split_by_n,
    CoTask,
    mlget as _
)
from collections import (
    deque
)
from binascii import (
    hexlify
)

# This module is partially based on: https://github.com/stef/pyrsp


def rsp_pack(data):
    " Formats data into a RSP packet "
    # c -> "}%s" % chr(ord(c) ^ 0x20)
    data = data.replace(b'}', b"}]")
    data = data.replace(b'*', b"}\n")
    data = data.replace(b'#', b"}\x03")
    data = data.replace(b'$', b"}\x04")
    return "$%s#%02x" % (data, (sum(ord(c) for c in data) % 256))


def rsp_check_pkt(data, checksum):
    return sum(ord(c) for c in data) % 256 == int(checksum, 16)


def rsp_decode(data):
    """ Decodes data from received packet.

    Decoding algorithm is described here:
    https://sourceware.org/gdb/onlinedocs/gdb/Overview.html
    """
    decoded_data = ""
    j = -1
    for i, ch in enumerate(data):
        if ch == '*' and data[i - 1] != '*':
            n = ord(data[i + 1]) - 29
            decoded_data = decoded_data + (data[i - 1] * n)
            j = i + 1
        elif i != j:
            decoded_data = decoded_data[::] + ch
    return decoded_data


class RSPReader(CoTask):
    def __init__(self, rsp):
        super(RSPReader, self).__init__(self.co_read(),
            description = _("RSP reader")
        )
        self.rsp = rsp

    def co_read(self):
        parser = self.co_parser()
        next(parser)

        # cache references
        rsp = self.rsp
        sock = rsp.sock
        read = sock.recv
        read_wait = sock, False
        send = parser.send

        while True:
            yield read_wait

            # `packet_size` is dynamic, do not cache!
            buf = read(rsp.packet_size)
            for c in buf:
                send(c)

    def co_parser(self):
        rsp = self.rsp

        # cache RSP callbacks
        write = rsp._write
        notify = rsp.__notification__
        packet = rsp.__packet__
        ack_ok = rsp.__ack_ok__
        ack_error = rsp.ack

        while True:
            c = yield
            if c == b"%":
                data = b""
                c = yield
                while c != b"#":
                    data += c
                    c = yield
                checksum = (yield) + (yield)

                print("-> %" + data + "#" + checksum)

                if rsp_check_pkt(data, checksum):
                    if rsp.ack: # `ack` is dynamic, do not cache!
                        write(b"+")
                    notify(data)
                else:
                    write(b"-")
            elif c == b"$":
                data = b""
                c = yield
                while c != b"#":
                    data += c
                    c = yield
                checksum = (yield) + (yield)

                print("-> $" + data + "#" + checksum)

                if rsp_check_pkt(data, checksum):
                    if rsp.ack:
                        write(b"+")
                    packet(data)
                else:
                    write(b"-")
            elif c == b"+":
                print("-> +")

                ack_ok()
            elif c == b"-":
                print("-> -")

                ack_error()
            else:
                raise RuntimeError("Unexpected character '%s'" % c)

    def on_failed(self):
        raise RuntimeError("CoRSP reader failed")


class RSPWriter(CoTask):

    def __init__(self, rsp):
        super(RSPWriter, self).__init__(self.co_write(),
            description = _("RSP writer")
        )
        self.rsp = rsp

    def co_write(self):
        # cache references
        rsp = self.rsp
        sock = rsp.sock
        write_wait = sock, True
        send = sock.send

        buf = rsp.out_buf
        rsp.out_buf = b""

        yield write_wait

        while True:
            if buf:
                sent = send(buf[:rsp.packet_size])
                if sent == len(buf):
                    buf = rsp.out_buf
                    rsp.out_buf = b""
                elif sent:
                    buf = buf[sent:]
                else:
                    yield write_wait
            else:
                yield False

                buf = rsp.out_buf
                rsp.out_buf = b""

    def on_failed(self):
        raise RuntimeError("CoRSP writer failed")


def assert_ok(data):
    if data != b"OK":
        raise RuntimeError("'OK' expected, got: '%s'" % data)


@notifier(
    "event" # CoRSP, data
  , "command" # CoRSP, data
)
class CoRSP(object):

    def __init__(self, co_disp, sock, verbose = False):
        self.sock = sock

        # using select based coroutines assumes that socket is non-blocking
        sock.setblocking(False)

        # operation parameters

        self.verbose = verbose
        # slow but safe, will overwritten during initialization sequence
        self.packet_size = 1

        self.ack = True

        # input

        self.acked = False

        co_disp.enqueue(RSPReader(self))

        # output

        # queue of requests scheduled by `send`
        self.waiting = deque()
        self.out_buf = b""

        co_disp.enqueue(RSPWriter(self))

    # events from reader
    def __packet__(self, data):
        waiting = self.waiting

        if not waiting:
            self.__notify_command(self, data)
            return

        callback = waiting.popleft()[2]

        if self.ack and not self.acked:
            raise RuntimeError("Packet has not been acked")
        self.acked = False

        if waiting:
            self._write(waiting[0][0])

        callback(data)

    def __notification__(self, data):
        self.__notify_event(self, data)

    def __ack_ok__(self):
        self.acked = True

    def __ack_error__(self):
        current = self.waiting[0]
        packet, retries, _ = current

        if retries == 0:
            raise RuntimeError("Packet sending retries exceeded")

        current[1] = retries - 1
        self._write(packet)

    # interaction with writer

    def send(self, data, callback = None, retries = 50):
        packet = rsp_pack(data)

        waiting = self.waiting
        waiting.append([packet, retries, callback])

        if len(waiting) == 1:
            self._write(packet)

    def _write(self, buf):
        print("<- " + buf)

        self.out_buf += buf

    # helpers

    def fetchOK(self, data):
        self.send(data, callback = assert_ok)

    def v_continue(self, pid_tid = "-1"):
        self.fetchOK("vCont;c:" + pid_tid)

    def v_step(self, pid_tid = "-1"):
        self.fetchOK("vCont;s:" + pid_tid)

    def finish(self):
        self.send("k")
        self.sock.close()

    def store(self, addr, data):
        for pkt in split_by_n(
            hexlify(data), self.packet_size - 20
        ):
            pktlen = len(pkt) / 2
            self.fetchOK("M%x,%x:%s" % (addr, pktlen, pkt))
            addr += pktlen


class CoRSPClient(CoRSP):

    def __init__(self, co_disp, remote, verbose = False):
        # connection setup
        addr, port = remote.split(":")

        sock = socket(AF_INET, SOCK_STREAM)
        while sock.connect_ex((addr, int(port))): pass

        super(CoRSPClient, self).__init__(co_disp, sock, verbose = verbose)

        self.selected_thread = None

        self.features = features = Features(
            multiprocess = True,
            qRelocInsn = True,
            swbreak = True
        )

        # begin initialization
        self._write(b"+")
        self.send(features.query(), callback = self._on_features)

    # initialization sequence (send-callback-send chain)
    def _on_features(self, data):
        features = self.features
        features.parse(data)
        self.packet_size = int(features["PacketSize"], 16)

        if not features["QNonStop"]:
            raise RuntimeError("Remote does not support non-stop mode")

        self.send("QNonStop:1", callback = self._on_nonstop)

    def _on_nonstop(self, data):
        assert_ok(data)
        if self.features["QStartNoAckMode"]:
            self.send("QStartNoAckMode", callback = self._on_noack)

    def _on_noack(self, data):
        assert_ok(data)
        self.ack = False

    # helpers

    def swap_thread(self, pid_tid):
        prev = self.selected_thread

        if prev != pid_tid:
            self.fetchOK("Hg" + pid_tid)
            self.selected_thread = pid_tid
        else:
            prev = None

        return prev

    def set_br(self, addr):
        self.swap_thread("p0.0")
        self.fetchOK("Z0,%s,1" % addr)

    def del_br(self, addr):
        self.swap_thread("p0.0")
        self.fetchOK("z0,%s,1" % addr)
