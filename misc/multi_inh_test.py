class C0(object):
    def __init__(self):
        print(type(self).__name__)

class C1(C0):
    def __init__(self):
        print("C1")
        super(C1, self).__init__()

class C2(C0):
    def __init__(self):
        print("C2")
        super(C2, self).__init__()

class C12(C1, C2): pass
class C21(C2, C1): pass

class C12i(C1, C2):
    def __init__(self):
        print("C12i")
        super(C12i, self).__init__()

if __name__ == "__main__":
    C12()
    C21()

    C12i()
