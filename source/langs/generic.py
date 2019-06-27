__all__ = [
    "INode"
  , "inodify_rule"
]


class INode(object):
    "Intermediate representation Node"

    def __init__(self, subtree):
        self.subtree = subtree

    def __getitem__(self, i):
        return self.subtree[i]

    def lr_iter(self, prod_name):
        """
Traverses left-recurrent productions like:

prod_name : prod1
          | prod_name prod2 prod3
          | prod_name prod4 TOKEN1

Such productions results in parse tree like:

 prod_name
   |   \
   |    prod1
   |
 prod_name
   |  \  \
   |   \  TOKEN1
   |    prod4
   |
 prod_name
      \  \
       \  prod3
       prod2

Yields right subtrees as lists.
Given the example above they could be such:

    [prod1], [prod4, TOKEN1], [prod2, prod3]

Note that the order is reversed relative to token stream (file) order, because
it is native for tree of left-recurrent production, ex.:

prd2 prod3 prod4 TOKEN1 prod1

        """
        cur = self.subtree
        while True:
            left = cur[0]
            if left.type != prod_name:
                yield cur[:]
                break
            else:
                right = cur[1:]
                yield right
                cur = left.value


def inodify_rule(p_func, globs_before):
    line = getattr(p_func, "co_firstlineno", p_func.__code__.co_firstlineno)
    code = "\n" * (line - 1) + """\
def _{p_func}(p):
    \"""{rule}\"""
    inode_class = {p_func}(p) or INode
    p[0] = inode_class(p.slice[1:])
""".format(
        p_func = p_func.__name__,
        rule = p_func.__doc__
    )
    exec(code, globs_before)
