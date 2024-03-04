__all__ = [
    "shadow_open"
]

from codecs import (
    open,
)
from contextlib import (
    contextmanager,
)
from os.path import (
    isfile,
)
from six import (
    StringIO,
)


@contextmanager
def shadow_open(filename):
    """ This context manager prevents the file from being overwritten with the
same content.
    """

    if isfile(filename):
        writer = StringIO()
        yield writer

        new_data = writer.getvalue().encode("utf-8")

        with open(filename, mode = "rb") as f:
            old_data = f.read()

        if old_data != new_data:
            with open(filename, mode = "wb") as f:
                f.write(new_data)
    else:
        with open(filename, mode = "wb", encoding = "utf-8") as f:
            yield f
