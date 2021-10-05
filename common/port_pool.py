__all__ = [
    "PortPool"
]

from .pypath import (
    pypath,
)
from collections import (
    namedtuple,
)
from socket import (
    socket,
    AF_INET,
    SOCK_STREAM,
    SOL_SOCKET,
    SO_REUSEADDR,
)
from threading import (
    Lock,
)
# use ours pyrsp
with pypath("..pyrsp"):
    from pyrsp.utils import (
        find_free_port,
    )


class PortPool(object):
    """ Grabs TCP ports from OS on demand and distribute them across customers
within the process.
    """

    def __init__(self):
        self.lock = Lock()
        self.free_ports = []
        # Free ports must remains ours.
        # For that purposes we `bind`s `socket`s to them.
        self.sockets = {}
        self.next_port = 1024

    def alloc_port(self):
        with self.lock:
            if self.free_ports:
                port = self.free_ports.pop()
                sock = self.sockets.pop(port)
                sock.close()
            else:
                port = find_free_port(self.next_port)
                while port is None:
                    # block until a port become free
                    port = find_free_port(1024)

                next_port = port + 1
                if next_port > 0xFFFF:
                    next_port = 1024

                self.next_port = next_port
            return port

    def free_port(self, port):
        with self.lock:
            self.sockets[port] = s = socket(AF_INET, SOCK_STREAM)
            s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            s.bind(("localhost", port))
            self.free_ports.append(port)

    def __call__(self):
        "Use as `with port_pool() as port:`"
        return _PortLease(self, self.alloc_port())


class _PortLease(namedtuple("_PortLease_", "pool port")):

    def __enter__(self):
        return self.port

    def __exit__(self, *__):
        self.pool.free_port(self.port)
