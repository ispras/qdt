from os.path import (
    join,
)
from .commit_note import (
    CommitNote,
)
from .conversation import (
    Conversation,
)
from common.gitproj.path_backed import (
    PathBackedCache,
)
from .merge_request import (
    MergeRequest,
)


class Context(object):

    def __init__(self, worktree_path):
        assert isinstance(worktree_path, tuple)

        self._worktree_path = worktree_path

        self._merge_requests = PathBackedCache(("merge_requests",),
            MergeRequest,
        )

        self._commit_notes_path = PathBackedCache(("commit_notes",),
            CommitNote
        )

        self._conversations = PathBackedCache(("conversations",),
            Conversation
        )

    def iter_merge_requests(self):
        return self._merge_requests.iter_file_backed()

    def iter_conversations(self):
        return self._conversations.iter_file_backed()

    def get_os_path(self, rel_path):
        return join(self._worktree_path + rel_path)
