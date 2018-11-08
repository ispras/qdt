__all__ = [
    "free_tcp_port"
]

from socket import (
    socket,
    AF_INET,
    SOCK_STREAM
)
from six.moves import (
    range
)

def free_tcp_port(first = 1024):
    for port in range(first, 1 << 16):
        test_socket = socket(AF_INET, SOCK_STREAM)
        try:
            test_socket.bind(("", port))
        except:
            pass
        else:
            return port
        finally:
            test_socket.close()

    raise RuntimeError("No free TCP port has been found")
