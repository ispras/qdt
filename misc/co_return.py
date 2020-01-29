""" How to return a value from coroutine in a Python portable way?
"""

from six import (
    PY2
)


def co_with_return():
    yield 1
    if PY2:
        raise StopIteration(2)
    else:
        # Py3 only
        # under Py2: SyntaxError: 'return' with argument inside generator
        # return 2

        # SyntaxError: 'return' outside function
        # exec("return 2")

        # XXX: will be error in future Py3 versions
        raise StopIteration(2)



def co_simple():
    yield 3
    yield 4


def do_probes(co_func):
    print(co_func.__name__)
    print("for:")
    for i in co_func():
        print(i)

    print("while:")
    co = co_func()

    try:
        while True:
            ret = next(co)
            print(ret)
    except StopIteration as e:
        # value = e.value # Py3 only
        try:
            value = e.args[0]
        except IndexError:
            value = None

        print(value)


if __name__ == '__main__':
    do_probes(co_with_return)
    do_probes(co_simple)
