from six.moves.tkinter import IntVar

ref_objects = {
    hash(None) : None
}

class ObjRefVar(IntVar):
    def __init__(self, *args, **kw):
        try:
            value = kw["value"]
        except KeyError:
            value = hash(None)
        else:
            value = hash(value)

        tmp = self.set
        # bypass Variable 'set' method calls from __init__
        self.set = lambda x : None

        IntVar.__init__(self, *args, **kw)

        self.set = tmp

        self.set(None)

    def set(self, value):
        h = hash(value)
        try:
            o = ref_objects[h]
        except KeyError:
            ref_objects[h] = value
        else:
            if value is not o:
                raise Exception("Both objects %s and %s have same hash 0x%x" %
                    str(o), str(value), h
                )

        IntVar.set(self, h)

    def get(self):
        h = IntVar.get(self)
        return ref_objects[h]
