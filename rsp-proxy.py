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
    CoRSP
)

def sigint(*a):
    global working
    if not working:
        print("Force exit")
        exit(-1)
    working = False

def co_accept(ss):
    while True:
        yield ss, False
        cs, caddr = ss.accept()
        print("connection from %s:%u" % caddr)
        cs.close()

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
    args = ap.parse_args()

    disp = CoDispatcher()

    # server socket
    port = free_tcp_port(args.start)
    ss = socket(AF_INET, SOCK_STREAM)
    ss.bind(("", port))
    ss.listen(10)

    print("Listening port %u" % port)

    disp.enqueue(co_accept(ss))

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
