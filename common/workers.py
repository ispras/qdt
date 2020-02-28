__all__ = [
    "PopenResult"
  , "PopenWorker"
  , "gen_pipe_reader"
]

from os.path import (
    split
)
from subprocess import (
    Popen,
    PIPE
)
from traceback import (
    print_exc
)
from threading import (
    Thread
)


class PopenResult(object):
    "A reference result stub implementation for `PopenWorker`."

    def __on_stdout__(self, line):
        pass

    def __on_stderr__(self, line):
        pass

    def __on_finish__(self, return_code, out_lines, err_lines):
        pass


class PopenWorker(object):

    def __init__(self, *args, **popen_kw):
        self.args = args
        self.popen_kw = popen_kw
        self.cmd_name = split(args[0])[1]

    def __str__(self):
        return " ".join(self.args)

    def __call__(self, result):
        proc = Popen(self.args,
            stdin = PIPE,
            stdout = PIPE,
            stderr = PIPE,
            **self.popen_kw
        )

        out, reader = gen_pipe_reader(proc.stdout, result.__on_stdout__)
        tout = Thread(
            target = reader,
            name = self.cmd_name + "_out"
        )
        err, reader = gen_pipe_reader(proc.stderr, result.__on_stderr__)
        terr = Thread(
            target = reader,
            name = self.cmd_name + "_err"
        )

        terr.start()
        tout.start()

        while proc.poll() is None:
            yield False

        try:
            result.__on_finish__(proc.returncode, out, err)
        except:
            print_exc()

        for t in [tout, terr]:
            while t.is_alive():
                yield False

            t.join()


def gen_pipe_reader(pipe, on_line):
    out = []

    def reader():
        for line in iter(pipe.readline, b""):
            try:
                on_line(line)
            except:
                print_exc()
            out.append(line)

    return out, reader
