__all__ = [
    "CoRSP"
      , "CoRSPClient"
  , "assert_ok"

  # Low level formatting
  , "rsp_escape_char"
  , "rsp_escape"
  , "rsp_unescape_parts"
  , "rsp_unescape"
  , "rsp_tail"
  , "rsp_packet"
  , "rsp_notification"
  , "rsp_check_pkt"
  , "rsp_decode"
  , "rsp_decode_parts"
  , "rsp_decode_chars"
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

_RSP_ESCAPE_TABLE = list(chr(code) for code in range(256))
# Some characters must be escaped

def rsp_escape_char(c):
    return '}' + chr(ord(c) ^ 0x20)

for c in "}*#$":
    _RSP_ESCAPE_TABLE[ord(c)] = rsp_escape_char(c)

# make it constant
RSP_ESCAPE_TABLE = tuple(_RSP_ESCAPE_TABLE)

def rsp_escape(data):
    "Escapes forbidden characters yielding substrings."
    for c in data:
        yield RSP_ESCAPE_TABLE[ord(c)]

def rsp_unescape_parts(data):
    "Decodes escaped characters yielding substrings."
    parts = data.split('}')
    i = iter(parts)
    prev = next(i)
    yield prev
    for cur in i:
        c = chr(ord(cur[0]) ^ 0x20)
        yield c
        yield cur[1:]

def rsp_unescape(data):
    return "".join(rsp_unescape_parts(data))

def rsp_tail(data):
    """ Evaluates tail of RSP command/response packet or notification with
checksum suffix, yielding substrings.
    """
    s = 0
    for part in rsp_escape(data):
        yield part
        for c in part:
            s += ord(c)
    yield "#%02x" % (s & 0xff)

def rsp_packet(data):
    "Escapes data and formats it into a RSP packet with honest checksum."
    return "$" + "".join(rsp_tail(data))

def rsp_notification(data):
    "Escapes data and formats it into a RSP notification with honest checksum."
    return "%" + "".join(rsp_tail(data))

def rsp_check_pkt(data, checksum):
    return sum(ord(c) for c in data) & 0xff == int(checksum, 16)

def rsp_decode(data):
    """ Decodes run-length encoded data.

See: https://sourceware.org/gdb/onlinedocs/gdb/Overview.html
    """
    return "".join(rsp_decode_parts(data))

def rsp_decode_parts(data):
    "An internal run-length decoding variant that yielding decoded substrings."
    parts = data.split('*')
    i = iter(parts)
    prev = next(i)
    yield prev
    for cur in i:
        n = ord(cur[0]) - 29
        yield prev[-1] * n
        yield cur[1:]
        prev = cur

def rsp_decode_chars(data):
    "A character generator variant of `rsp_decode`."
    for part in rsp_decode_parts(data):
        for c in part:
            yield c

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
                        notify(data, checksum)
                    else:
                        write(b"-")
                else:
                    notify(data, checksum)
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
                        packet(data, checksum)
                    else:
                        write(b"-")
                else:
                    packet(data, checksum)
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


def assert_ok(data, _):
    if data != b"OK":
        raise RuntimeError("'OK' expected, got: '%s'" % data)


@notifier(
    "event" # CoRSP, data, checksum
  , "command" # CoRSP, data, checksum
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
    def __packet__(self, data, checksum):
        waiting = self.waiting

        if not waiting:
            self.__notify_command(self, data, checksum)
            return

        if self._ack:
            callback = waiting[0][2]

            if callback is None:
                # Current packet waits for ack, not for a response. Hence,
                # this packet is a command.
                self.__notify_command(self, data, checksum)
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

        callback(data, checksum)

    def __notification__(self, data, checksum):
        self.__notify_event(self, data, checksum)

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

    def packet(self, data, *a, **kw):
        """Formats `data` as RSP packet (command or response) and queue it to
send. See backing `send` for arguments and return value descriptions.
        """
        packet = rsp_packet(data)
        return self.send(packet, *a, **kw)

    def send(self, packet, callback = None, retries = 50):
        """ `None` `callback` means that no response packet is expected. It is
useful for a packet which is a response itself.
        """

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
        print("<- " + repr(buf))

        self.out_buf += buf

    # helpers

    def fetchOK(self, data):
        self.packet(data, callback = assert_ok)

    def v_continue(self, pid_tid = "-1"):
        self.fetchOK("vCont;c:" + pid_tid)

    def v_step(self, pid_tid = "-1"):
        self.fetchOK("vCont;s:" + pid_tid)

    def finish(self):
        self.packet("k")
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
        self.packet(features.resuest(), callback = self._on_features)

    # initialization sequence (send-callback-send chain)
    def _on_features(self, data, _):
        self.stub_features = features = Features.parse(data)
        self.packet_size = int(features["PacketSize"], 16)

        if not features["QNonStop"]:
            raise RuntimeError("Remote does not support non-stop mode")

        self.packet("QNonStop:1", callback = self._on_nonstop)

    def _on_nonstop(self, data, _):
        assert_ok(data)
        if self.stub_features["QStartNoAckMode"]:
            self.packet("QStartNoAckMode", callback = self._on_noack)

    def _on_noack(self, data, _):
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
