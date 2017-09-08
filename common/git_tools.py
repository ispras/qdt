__all__ = [
    "CommitDesc"
]

class CommitDesc(object):
    def __init__(self, sha, parents, children):
        self.sha = sha
        self.parents = parents
        self.children = children

        # serial number according to the topological sorting
        self.num = None
