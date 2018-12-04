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
        self.target = proxy['self'].target

    def __getattr__(self, attr):
        # TODO: Delete it
        if self.key == 'ch':
            self.debug_process.cb[self.key](self.__lineno, attr)
        return 0

    def __getitem__(self, key):
        self.key = key
        if self.__lineno in self.target.elf.src_map:
            if key in self.debug_process.cb:
                # TODO: Delete it
                if key != 'ch':
                    self.debug_process.cb[key](self.__lineno)
                return self
            else:
                print("Warning: command '%s' is not defined!" % key)
                return self.__proxy[key]
        else:
            print("Warning: line number '%s' is not found!" % self.__lineno)
        return 0
