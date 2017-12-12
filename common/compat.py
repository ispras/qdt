def execfile(filename, globals = None, locals = None):
    f = open(filename, "rb")
    content = f.read()
    f.close()
    obj = compile(content, filename, "exec")

    if globals is None:
        globals = {}

    globals["__file__"] = filename
    globals["__name__"] = "__main__"

    exec(content, globals, locals)
