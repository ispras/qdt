__all__ = [
    "GitSearchRuntime"
      , "E_GIT_FOUND"
      , "E_GIT_DISCARD_FOUND"
  , "GitSearchRequest"
      , "git_feature_commit_hexsha"
  , "GitSearchResult"
]

from ..bidict import (
    bidict,
)
from ..events import (
    notify,
)

from collections import (
    defaultdict,
)
from itertools import (
    chain,
)


def git_feature_commit_hexsha(commit, hexsha, **ignored):
    return commit.hexsha == hexsha


class GitSearchResult:

    def __init__(self, req, commit):
        self.req = req
        self.commit = commit


class GitSearchRequest:

    def __init__(self, features, criteria):
        self.features = features
        self.criteria = criteria

    def probe(self, commit):
        criteria = self.criteria
        for f in self.features:
            if f(commit, **criteria):
                return GitSearchResult(self, commit)


E_GIT_FOUND = "git_found"
E_GIT_DISCARD_FOUND = "git_discard_found"

class GitSearchRuntime:

    def __init__(self, task_manager):
        self.req2co = req2co = bidict()
        self.co2req = req2co.mirror
        self.tm = task_manager
        self.commits = []
        self.req2ress = defaultdict(list)
        self.c2ress = defaultdict(list)

    def account_commits(self, *commits):
        self.commits.extend(commits)

    def account_requests(self, *reqs):
        acc = self.account_request
        for r in reqs:
            acc(r)

    def account_request(self, r):
        co = self._co_search(r)
        self.req2co[r] = co
        self.tm.enqueue(co)

    def remove_requests(self, *reqs):
        remove = self.remove_request
        for r in reqs:
            remove(r)

    def remove_request(self, req):
        co = self.req2co.pop(req)
        self.tm.cancel_task(co)
        for res in self.req2ress.pop(req):
            notify(self, E_GIT_DISCARD_FOUND, result = res)
            self.c2ress[res.commit].remove(res)

    def remove_all_requests(self):
        co2req = self.co2req
        coroutines = tuple(co2req)
        co2req.clear()
        cancel = self.tm.cancel_task
        for co in coroutines:
            cancel(co)
        ress = tuple(chain(*self.req2ress.values()))
        self.req2ress.clear()
        self.c2ress.clear()
        for res in ress:
            notify(self, E_GIT_DISCARD_FOUND, result = res)

    def cleanup(self):
        self.remove_all_requests()
        self.commits *= 0

    def _co_search(self, req):
        commit_idx = 0
        commits = self.commits
        probe = req.probe
        n = 0
        while True:
            if commit_idx < len(commits):
                if n == 30:
                    yield True
                    n = 0
                else:
                    n += 1
            else:
                yield False
                # wait for more commits
                continue
            commit = commits[commit_idx]
            res = probe(commit)
            if res is not None:
                self.req2ress[res.req].append(res)
                self.c2ress[commit].append(res)
                notify(self, E_GIT_FOUND, result = res)
            commit_idx += 1

    def get_commit_results(self, c):
        ret = self.c2ress.get(c)
        if ret is not None:
            return ret.copy()
