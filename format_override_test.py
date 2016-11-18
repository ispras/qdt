class MyStr(str):
    def __format__(self, *args, **kwargs):
        print "my format"
        return str.__format__(self, *args, **kwargs)

    def __mod__(self, *args, **kwargs):
        print "mod"
        return str.__mod__(self, *args, **kwargs)


if __name__ == "__main__":
    ms = MyStr("- %s - {} -")
    print ms.format("test")
    print ms % "test"
