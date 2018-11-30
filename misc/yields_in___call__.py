class Co(object):

    def __init__(self, v):
        self.v = v

    def __call__(self):
        yield self.v


if __name__ == "__main__":
    c = Co(1)
    for v in c():
        print(v)
