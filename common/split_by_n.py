__all__ = [
    "split_by_n"
]


def split_by_n(seq, n):
    """ A generator to divide a sequence into chunks of n units.

    Source:
    http://stackoverflow.com/questions/9475241/split-python-string-every-nth-character
    """
    while seq:
        yield seq[:n]
        seq = seq[n:]
