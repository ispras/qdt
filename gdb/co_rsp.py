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


def rsp_escape(data):
    # c -> "}%s" % chr(ord(c) ^ 0x20)
    data = data.replace(b'}', b"}]")
    data = data.replace(b'*', b"}\n")
    data = data.replace(b'#', b"}\x03")
    data = data.replace(b'$', b"}\x04")
    return data

def rsp_pack(data):
    "Formats data into a RSP packet"
    return "$%s#%02x" % (rsp_escape(data), (sum(ord(c) for c in data) % 256))


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
        recv = sock.recv
        read_wait = sock, False
        send = parser.send

        while True:
            yield read_wait

            # 0xFFFF - 20 [minimum IP header length] = 65515
            # It's the maximum size of an IP packet payload.
            # See: https://tools.ietf.org/rfc/rfc791.txt
            # Note that normal gdbserver `PacketSize` is 0x3fff. Which is much
            # less than this limit. So, the reader may always accept an entire
            # RSP packet per `recv` call.
            buf = recv(65515)
            for c in buf:
                send(c)

    def co_parser(self):
        rsp = self.rsp

        # cache RSP callbacks
        write = rsp._write
        notify = rsp.__notification__
        packet = rsp.__packet__
        ack_ok = rsp.__ack_ok__
        ack_error = rsp.__ack_error__

        while True:
            c = yield
            if c == b"%":
                data = b""
                c = yield
                while c != b"#":
                    data += c
                    c = yield
                checksum = (yield) + (yield)

                print("-> " + repr("%" + data + "#" + checksum))

                if rsp._ack: # `_ack` is dynamic, do not cache!
                    if rsp_check_pkt(data, checksum):
                        write(b"+")
                        notify(data)
                    else:
                        write(b"-")
                else:
                    notify(data)
            elif c == b"$":
                data = b""
                c = yield
                while c != b"#":
                    data += c
                    c = yield
                checksum = (yield) + (yield)

                print("-> " + repr("$" + data + "#" + checksum))

                if rsp._ack:
                    if rsp_check_pkt(data, checksum):
                        write(b"+")
                        packet(data)
                    else:
                        write(b"-")
                else:
                    packet(data)
            elif c == b"+":
                print("-> +")

                ack_ok()
            elif c == b"-":
                if rsp._ack:
                    # While "+" packets are still acceptable in no-ack mode, a
                    # "-" packet is direct protocol violation. Because this
                    # side should neither expect nor handle them.
                    print("-> - [unexpected in no-ack mode]")
                else:
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
                # `packet_size` is dynamic, do not cache!
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

        self._ack = True

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

        if self._ack:
            callback = waiting[0][2]

            if callback is None:
                # Current packet waits for ack, not for a response. Hence,
                # this packet is a command.
                self.__notify_command(self, data)
                return

            if not self.acked:
                raise RuntimeError("Packet has not been acked")

            waiting.popleft()

            if waiting:
                self._write(waiting[0][0])
                self.acked = False
        else:
            callback = waiting.popleft()[2]
            # Note that because of no-ack mode operation algorithms, `waiting`
            # does always contain a packet with a response expected at the
            # moment of `__packet__` call beginning.
            # So, `callback` is never `None`.

            self._flush()

        callback(data)

    def __notification__(self, data):
        self.__notify_event(self, data)

    def __ack_ok__(self):
        if not self._ack:
            return

        # packets sent without a callback is expected to have no feedback data
        waiting = self.waiting

        callback = waiting[0][2]
        if callback is None:
            waiting.popleft()
            if waiting:
                self._write(waiting[0][0])
        else:
            self.acked = True

    def __ack_error__(self):
        current = self.waiting[0]
        packet, retries, _ = current

        if retries == 0:
            raise RuntimeError("Packet sending retries exceeded")

        current[1] = retries - 1
        self._write(packet)

    # interaction with writer
    @property
    def ack(self):
        return self._ack

    @ack.setter
    def ack(self, v):
        if self._ack == v:
            return
        self._ack = v

        if v:
            if self.waiting:
                self.acked = False
            return

        # Entering no-ack mode.
        self._flush()


    def _flush(self):
        """ Flushes all packets without a response expected until one which do
expect. """
        waiting = self.waiting

        if not waiting:
            return

        callback = waiting[0][2]
        while callback is None:
            waiting.popleft()
            if not waiting:
                break
            packet, _, callback = waiting[0]
            self._write(packet)

    def send(self, data, callback = None, retries = 50):
        """ `None` `callback` means that no response packet is expected. It is
useful for a packet which is a response itself.
        """
        packet = rsp_pack(data)

        waiting = self.waiting
        if self._ack:
            if not waiting:
                self.acked = False
                self._write(packet)
            # Because of ack mode even a packet with no response expected
            # should be preserved in `waiting` for possible re-sending.
            waiting.append([packet, retries, callback])
        else:
            if waiting:
                # Note that because of no-ack mode operation algorithms,
                # `waiting` must contain at least one packet with response
                # expected.
                # So, appending this packet to the `waiting` queue
                # will not result in its hanging.
                # It will be sent during handling of a response for previous
                # packet in `waiting` during `__packet__` operation.
                waiting.append([packet, retries, callback])
            else:
                if callback is not None:
                    # A response is expected for this packet.
                    waiting.append([packet, retries, callback])
                # else:
                    # Because of no-ack mode, a re-sending is never required
                    # and this packet copy should not be kept in `waiting`.

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
        self.send(features.resuest(), callback = self._on_features)

    # initialization sequence (send-callback-send chain)
    def _on_features(self, data):
        self.stub_features = features = Features.parse(data)
        self.packet_size = int(features["PacketSize"], 16)

        if not features["QNonStop"]:
            raise RuntimeError("Remote does not support non-stop mode")

        self.send("QNonStop:1", callback = self._on_nonstop)

    def _on_nonstop(self, data):
        assert_ok(data)
        if self.stub_features["QStartNoAckMode"]:
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
