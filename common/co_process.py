__all__ = [
    "co_process"
  , "FunctionFailure"
]

from multiprocessing import (
    Pipe,
    Process
)
from sys import (
    exc_info
)
from .co_dispatcher import (
    CoReturn
)


class FunctionFailure(RuntimeError): pass


def co_process(function, *a, **kw):
    """ Call the `function` in a dedicated process, `a` & `kw` are for
the call.
    """

    in_, out = Pipe(False)
    proc = Process(
        target = caller,
        args = (out, function, a, kw)
    )
    proc.start()
    while proc.is_alive():
        yield False

    if proc.exitcode:
        raise RuntimeError(
            "process with function %s has ended with return code %s" % (
                function, proc.exitcode
            )
        )

    kind, payload = in_.recv()
    if kind == 0: # normal return
        raise CoReturn(payload)
    else: # 1 the function failed
        raise FunctionFailure(*payload)


def caller(feedback, function, a, kw):
    try:
        ret = function(*a, **kw)
    except:
        feedback.send((1, exc_info()))
    else:
        feedback.send((0, ret))
