from common.git_tools import (
    co_build_git_graph,
    CommitDesc,
)

from collections import (
    defaultdict,
)


class GitMgNode(CommitDesc):
    """
Notes:

- A macronode is a commit with some non-regularity.
    E.g. tag or head.
    Roots, forks & merges are macronodes too.

- `_edge` attribute refers to `GitMgEdge` that node belongs to.
    It's `None` for macronodes.

    """

    def __init__(self, mg, sha, **kw):
        super(GitMgNode, self).__init__(sha, **kw)
        self._mg = mg

    def add_child(self, *a, **kw):
        super(GitMgNode, self).add_child(*a, **kw)
        if self.is_fork:
            self._mg._account_macronode(self)

    _edge = None


class GitMgEdge(list):
    """ It's a sequence of commits (from `all_nodes`) between macronodes.

Notes:

- `_ancestor` attribute refers to parent (a macronode) of first node.

- `_descendant` attribute refers to child (a macronode) of last node.

    """
    __hash__ = lambda self: id(self)


class GitMacrograph(object):

    def __init__(self, repo):
        self._repo = repo

    def _node_factory(self, sha):
        node = GitMgNode(self, sha)
        if sha in self._sha2ref:
            self._account_macronode(node)  # tag/head
        else:
            commit = self._repo.commit(sha)
            parents = commit.parents
            if not parents:  # a root
                self._account_macronode(node)
            elif len(parents) > 1:  # a merge
                self._account_macronode(node)
            # Note, children are not known right now.
            # So, fork macronodes are detected by `GitMgNode.add_child`
            #   at runtime of `co_build`.
        return node

    built = False

    def co_build(self, **kw):
        repo = self._repo
        self._sha2ref = dict((r.commit.hexsha, r) for r in repo.references)

        # Keys are macronodes (`GitMgNode`).
        # Values are `set`s of `GitMgEdge`
        self._edges = defaultdict(set)

        self._all_nodes = all_nodes = {}

        self._edges2build = []

        yield True

        for co_bgg_ready in co_build_git_graph(repo, all_nodes,
            node_factory = self._node_factory,
            **kw
        ):
            yield self._co_build_edges()
            yield co_bgg_ready

        # process edges added during last iteration
        yield self._co_build_edges()

        self.built = True

    def _co_build_edges(self):
        # cache
        edges2build = self._edges2build
        edges = self._edges

        while edges2build:
            yield True
            e = edges2build.pop()

            while True:
                children = e[-1].children
                assert len(children) == 1
                c = children[0]
                if c in edges:
                    # macronode
                    e._descendant = c
                    break
                else:
                    c._edge = e
                    e.append(c)

    # Note: This method must return as fast as possible!
    #     ` All intensive work must be delegated to `co_build`.
    def _account_macronode(self, mn):
        edges = self._edges

        # edges from macronode `mn` to its descendant macronodes
        mn2dmns = edges[mn]

        print("macronode: ", mn.sha, " total: ", len(edges))

        if mn._edge is not None:
            # print("a macronode is detected on edge")
            assert mn.is_fork

            e = mn._edge

            try:
                self._edges2build.remove(e)
            except ValueError:
                # print("that edge is already built")
                # split in 2 edges
                # TODO: Edge splittimg may take a while on long edges.
                #       Consider moving this action to `co_build`, like edge
                #       construction.
                i = e.index(mn)
                e2 = GitMgEdge(e[i+1:])
                del e[i:]
                for n in e2:
                    n._edge = e2
                e2._ancestor = mn
                e2._descendant = e._descendant
                e._descendant = mn
                mn2dmns.add(e2)
            else:
                # print("that edge is not yet built")
                # Because `mn` is a node the edge entering. the edge is
                # considered built.
                # Note. there are no intermediate commits.
                assert len(e) == 1
                e.remove(mn)
                e._descendant = mn

            del mn._edge

        while len(mn2dmns) < len(mn.children):
            # begin edge construction for new children
            for c in mn.children:
                # try to find an edge containing this `c`hild
                # A `c`hild can be another macronode so edge between
                # is empty but have `_descendant is c`.
                for e in mn2dmns:
                    if (
                           (e and e[0] is c)
                        or getattr(e, "_descendant", None) is c
                    ):
                        break
                else:
                    e = GitMgEdge()
                    e._ancestor = mn
                    if c in edges:
                        # Child is a macronode too.
                        e._descendant = c
                    else:
                        c._edge = e
                        e.append(c)
                        self._edges2build.append(e)
                    mn2dmns.add(e)
