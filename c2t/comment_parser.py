__all__ = [
    "CommentParser"
]


class CommentParser(dict):
    """ This class parses test source file and extracts breakpoint positions
    """

    def __init__(self, proxy, lineno):
        dict.__init__(self)
        self.__proxy = proxy
        self.__lineno = lineno
        self.debug_process = proxy['self']

    def __getattr__(self, attr):
        # TODO: Delete it
        if self.key == 'ch' or self.key == 'chc':
            self.debug_process(self.key, self.__lineno, attr)
        else:
            print("Warning: command '%s' has not attributes, line: %s" % (
                self.key, self.__lineno
            ))
        return 0

    def __getitem__(self, key):
        self.key = key
        try:
            self.debug_process(key, self.__lineno)
        except RuntimeError:
            print("Warning: command '%s' is not defined, line: %s" % (
                self.key, self.__lineno
            ))
            # TODO: return it or not return it
            # return self.__proxy[key]
        return self
