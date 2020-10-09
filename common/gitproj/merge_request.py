from os.path import (
    join,
    isfile,
)
from ..lazy import (
    lazy,
)
from ..filefilter import (
    filefilter,
)
from .path_backed import (
    PathBacked,
    PathBackedCache,
)
from .message import (
    Message,
)


DESCRIPTION_FF = filefilter([(True, "description(?:\..+)")])


class MergeRequest(PathBacked):

    DESCRIPTION_FNAME = "description.md"
    TARGET_BRANCH_FNAME = "target_branch.txt" # think about Windows too
    STATUS_FNAME = "status.txt"

    def __init__(self, *a, **kw):
        super(MergeRequest, self).__init__(*a, **kw)

        self._conversation = PathBackedCache(
            self._relpath + ("conversation",),
            Message
        )

    def iter_messages(self):
        return self._conversation.iter_file_backed()

    @lazy
    def description_os_path(self):
        for name in DESCRIPTION_FF.find_files(self.os_path)[2]:
            os_path = join(self.os_path, name)
            if isfile(os_path):
                return os_path

        return join(self.os_path, self.DESCRIPTION_FNAME)

    @property
    def description(self):
        with open(self.description_os_path, "r") as f:
            return f.read()

    @lazy
    def target_branch_os_path(self):
        return join(self.os_path, self.TARGET_BRANCH_FNAME)

    @property
    def target_branch(self):
        with open(self.target_branch_os_path, "r") as f:
            return f.readline().strip()

    @lazy
    def status_os_path(self):
        return join(self.os_path, self.STATUS_FNAME)

    @property
    def status(self):
        with open(self.status_os_path, "r") as f:
            return f.readline().strip()
