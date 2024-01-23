from timeit import timeit
from collections import deque



def t1():
    l = []
    i = 0
    while i < 50000:
        l.append(i)
        i += 1


print(timeit(t1, number = 1000))


def t2():
    q = deque()
    i = 0
    while i < 50000:
        q.append(i)
        i += 1
    l = [None] * len(q)
    l[:] = q


print(timeit(t2, number = 1000))


def t3():
    l = [None] * 50000


print(timeit(t3, number = 1000))


def t4():
    q = deque()
    i = 0
    while i < 50000:
        q.append(i)
        i += 1


print(timeit(t4, number = 1000))


def t5():
    i = 0
    while i < 50000:
        i += 1


print(timeit(t5, number = 1000))


def t6():
    for i in range(50000):
        pass


print(timeit(t6, number = 1000))


def t7():
    q = deque()
    for i in range(50000):
        q.append(i)


print(timeit(t7, number = 1000))
