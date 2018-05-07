from sys import exc_info
from time import time

def gen1():
    print("1.1")
    yield
    print("1.2")
    raise StopIteration()

def gen2():
    print("2.1")
    yield
    print("2.2")
    return

def gen3():
    print("3.1")
    yield
    print("3.2")
    raise RuntimeError()

def gen4():
    print("4.1")
    yield
    if int(time()) % 2:
        print("4.2-1")
        return
    else:
        print("4.2-2")
        return

def gen5():
    yield

for gen in [ g for n, g in globals().items() if n.startswith("gen") ]:
    g = gen() # launch the generator
    gi_frame = g.gi_frame
    while True:
        try:
            next(g)
        except StopIteration: # generator normally returned
            tb = exc_info()[2].tb_next
            if tb is None:
                print("last line: %s" % gi_frame.f_lineno)
            else:
                print("last line: %s" % tb.tb_frame.f_lineno)
            break
        except BaseException: # generator failure
            tb = exc_info()[2].tb_next
            print("last line: %s" % tb.tb_frame.f_lineno)
            break
        else:
            print("last line: %s" % g.gi_frame.f_lineno)
