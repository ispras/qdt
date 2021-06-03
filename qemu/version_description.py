__all__ = [
    "ProcessingUntrackedFile"
  , "ProcessingModifiedFile"
  , "QVCWasNotInitialized"
  , "BadBuildPath"
  , "QVCIsNotReady"
  , "QemuVersionDescription"
  , "qvd_get"
  , "qvds_load"
  , "qvd_load_with_cache"
  , "qvds_load_with_cache"
  , "qvds_init_cache"
  , "forget_build_path"
  , "load_build_path_list"
  , "account_build_path"
]

from source import (
    SourceTreeContainer,
    Header,
    Macro
)
from common import (
    rename_replacing,
    git_find_commit,
    co_process,
    get_cleaner,
    lazy,
    CancelledCallee,
    FailedCallee,
    fast_repo_clone,
    fixpath,
    CommitDesc,
    mlget as _,
    callco,
    remove_file,
    execfile,
    pythonize
)
from collections import (
    defaultdict
)
from .version import (
    QVHDict,
    initialize_version,
    qemu_heuristic_db,
    calculate_qh_hash,
    get_vp
)
from .qom_hierarchy import (
    QType,
    co_update_device_tree
)
from os import (
    listdir
)
from os.path import (
    sep,
    join,
    isfile
)
from .pci_ids import (
    PCIId,
    PCIClassification
)
from git import (
    Repo
)
from six import (
    u
)
from shutil import (
    rmtree
)
from traceback import (
    format_exception
)
from sys import (
    exc_info
)


bp_file_name = "build_path_list"

# Two level dict:
# 1. path (of Qemu Git repo)
# 2. Qemu version (SHA1 id of Git commit)
qvd_reg = None

class ProcessingUntrackedFile(RuntimeError):
    def __init__(self, file_name):
        super(ProcessingUntrackedFile, self).__init__(file_name)

    def __str__(self):
        return (_("Source has untracked file: %s.") % self.args[0]).get()

class ProcessingModifiedFile(RuntimeError):
    def __init__(self, file_name):
        super(ProcessingModifiedFile, self).__init__(file_name)

    def __str__(self):
        return (_("Source has modified file: %s.") % self.args[0]).get()

def load_build_path_list():
    global qvd_reg

    if qvd_reg is not None:
        return

    qvd_reg = {}

    if not isfile(bp_file_name):
        return

    with open(bp_file_name) as f:
        build_path_list = f.readlines()

    for val in build_path_list:
        v = val.rstrip()
        qvd_reg[v] = {}

def account_build_path(path):
    load_build_path_list()

    if path in qvd_reg.keys():
        return
    if not isfile(bp_file_name):
        f = open(bp_file_name, 'w')
    else:
        f = open(bp_file_name, 'a')

    f.write(path + "\n")
    f.close()

    qvd_reg[path] = {}

def forget_build_path(path):
    load_build_path_list()

    if not path in qvd_reg.keys():
        raise RuntimeError("%s is not registered." % path)

    del qvd_reg[path]

    with open(bp_file_name, 'w') as f:
        f.write("\n".join(qvd_reg.keys()))

def qvd_get(path, version = None):
    load_build_path_list()

    if path is None:
        raise BadBuildPath("Build path is None.")

    try:
        qvds = qvd_reg[path]
    except KeyError:
        # before accounting because it can raise an exception
        qvd = QemuVersionDescription(path, version = version)
        account_build_path(path)
        qvd_reg[path][qvd.commit_sha] = qvd
        return qvd

    if version is None and qvds:
        # Legacy behavior. Return QVD for HEAD if version is omitted.
        # Note, Git repository at this path can be obtained from any QVD.
        version = next(iter(qvds.values())).repo.head.commit.hexsha

    try:
        return qvds[version]
    except KeyError:
        qvd = QemuVersionDescription(path, version = version)
        # Version aliasing is possible. SHA1 is an invariant. Return existing
        # QVD instead of just created one.
        return qvds.setdefault(qvd.commit_sha, qvd)

def qvd_load_with_cache(build_path, version = None):
    qvd = qvd_get(build_path, version = version)
    qvd.init_cache()
    return qvd

def qvds_load():
    load_build_path_list()

    for path in list(qvd_reg):
        qvd_get(path)

def qvds_init_cache():
    if qvd_reg is None:
        return

    for qvds in qvd_reg.values():
        for v in qvds:
            if v.qvc is None:
                v.init_cache()

def qvds_load_with_cache():
    qvds_load()
    qvds_init_cache()

class QemuCommitDesc(CommitDesc):
    def __init__(self, sha, parents, children):
        super(QemuCommitDesc, self).__init__(sha, parents, children)

        # dict of QEMUVersionParameterDescription new_value parameters
        self.param_nval = {}
        # dict of QEMUVersionParameterDescription old_value parameters
        self.param_oval = {}

class QemuVersionCache(object):
    current = None

    def __init__(self,
        list_headers = None,
        device_tree = None,
        known_targets = None,
        version_desc = None,
        pci_classes = None
    ):
        self.device_tree = device_tree
        self.known_targets = known_targets
        self.list_headers = list_headers
        self.version_desc = version_desc

        # Create source tree container
        self.stc = SourceTreeContainer()
        self.pci_c = PCIClassification() if pci_classes is None else pci_classes

    def co_computing_parameters(self, repo, version):
        print("Build QEMU Git graph ...")
        self.commit_desc_nodes = {}
        yield QemuCommitDesc.co_build_git_graph(repo, self.commit_desc_nodes)
        print("QEMU Git graph was built")

        yield self.co_propagate_param()

        c = self.commit_desc_nodes[repo.commit(version).hexsha]
        param = self.version_desc = QVHDict()
        for k, v in c.param_nval.items():
            param[k] = v
        for k, v in c.param_oval.items():
            param[k] = v

    def co_propagate_param(self):
        vd = qemu_heuristic_db
        vd_list = []

        unknown_vd_keys = set()
        for k in vd.keys():
            if k in self.commit_desc_nodes:
                vd_list.append((k, self.commit_desc_nodes[k].num))
            else:
                unknown_vd_keys.add(k)
                print("WARNING: Unknown SHA1 %s in QEMU heuristic database" % k)

        sorted_tuple = sorted(vd_list, key = lambda x: x[1])
        sorted_vd_keys = [t[0] for t in sorted_tuple]

        yield True

        # first, need to propagate the new labels
        print("Propagation params in graph of commit's description ...")
        yield self.co_propagate_new_param(sorted_vd_keys, vd)
        yield self.co_propagate_old_param(sorted_vd_keys, unknown_vd_keys, vd)
        print("Params in graph of commit's description were propagated")

    def co_propagate_new_param(self, sorted_vd_keys, vd):
        """ This method propagate QEMUVersionParameterDescription.new_value
        in graph of commits. It must be called before old_value propagation.

    :param sorted_vd_keys:
        keys of qemu_heuristic_db sorted in ascending order by num of
        QemuCommitDesc. It's necessary to optimize the graph traversal.

    :param vd:
        qemu_heuristic_db
        """

        # iterations to yield
        i2y = QVD_HP_IBY

        for key in sorted_vd_keys:
            cur_vd = vd[key]
            cur_node = self.commit_desc_nodes[key]
            for vpd in cur_vd:
                cur_node.param_nval[vpd.name] = vpd.new_value

            if i2y == 0:
                yield True
                i2y = QVD_HP_IBY
            else:
                i2y -= 1

        # vd_keys_set is used to accelerate propagation
        vd_keys_set = set(sorted_vd_keys)

        # old_val contains all old_value that are in ancestors
        old_val = {}
        for key in sorted_vd_keys:
            stack = [self.commit_desc_nodes[key]]
            for vpd in vd[key]:
                try:
                    old_val[vpd.name].append(vpd.old_value)
                except KeyError:
                    old_val[vpd.name] = [vpd.old_value]
            while stack:
                cur_node = stack.pop()
                for c in cur_node.children:
                    if c.sha in vd_keys_set:
                        # if the child is vd, only the parameters that are not
                        # in vd's param_nval are added
                        for p in cur_node.param_nval:
                            if p not in c.param_nval:
                                c.param_nval[p] = cur_node.param_nval[p]
                        # no need to add element to stack, as it's in the sorted_vd_keys
                    else:
                        # the child is't vd
                        for p in cur_node.param_nval:
                            if p in c.param_nval:
                                if cur_node.param_nval[p] != c.param_nval[p]:
                                    exc_raise = False
                                    if p in old_val:
                                        if cur_node.param_nval[p] not in old_val[p]:
                                            if c.param_nval[p] in old_val[p]:
                                                c.param_nval[p] = cur_node.param_nval[p]
                                                stack.append(c)
                                            else:
                                                exc_raise = True
                                    else:
                                        exc_raise = True
                                    if exc_raise:
                                        raise Exception("Contradictory definition of param " \
"'%s' in commit %s (%s != %s)" % (p, c.sha, cur_node.param_nval[p], c.param_nval[p])
                                        )
                            else:
                                c.param_nval[p] = cur_node.param_nval[p]
                                stack.append(c)

                if i2y == 0:
                    yield True
                    i2y = QVD_HP_IBY
                else:
                    i2y -= 1

    def co_propagate_old_param(self, sorted_vd_keys, unknown_vd_keys, vd):
        """ This method propagate QEMUVersionParameterDescription.old_value
        in graph of commits. It must be called after new_value propagation.

    :param sorted_vd_keys:
        keys of qemu_heuristic_db sorted in ascending order by num of
        QemuCommitDesc. It's necessary to optimize the graph traversal.

    :param unknown_vd_keys:
        set of keys which are not in commit_desc_nodes.

    :param vd:
        qemu_heuristic_db
        """

        # message for exceptions
        msg = "Conflict with param '%s' in commit %s (old_val (%s) != old_val (%s))"

        # iterations to yield
        i2y = QVD_HP_IBY

        # Assume unknown SHA1 corresponds to an ancestor of a known node.
        # Therefore, old value must be used for all commits.
        for commit in self.commit_desc_nodes.values():
            for vd_keys in unknown_vd_keys:
                self.init_commit_old_val(commit, vd[vd_keys])

                i2y -= 1
                if not i2y:
                    yield True
                    i2y = QVD_HP_IBY

        vd_keys_set = set(sorted_vd_keys)
        visited_vd = set()
        for key in sorted_vd_keys[::-1]:
            stack = []
            # used to avoid multiple processing of one node
            visited_nodes = set([key])
            visited_vd.add(key)

            node = self.commit_desc_nodes[key]
            for p in node.parents:
                stack.append(p)

                # propagate old_val from node to their parents
                p.param_oval.update()
                for param, oval in node.param_oval.items():
                    try:
                        other = p.param_oval[param]
                    except KeyError:
                        p.param_oval[param] = oval
                    else:
                        if other != oval:
                            raise Exception(msg % (param, p.sha, oval, other))

                # init old_val of nodes that consist of vd's parents
                # and check conflicts
                self.init_commit_old_val(p, vd[key])

                i2y -= 1
                if not i2y:
                    yield True
                    i2y = QVD_HP_IBY

            while stack:
                cur_node = stack.pop()
                visited_nodes.add(cur_node.sha)

                for commit in cur_node.parents + cur_node.children:
                    if commit.sha in visited_nodes:
                        continue
                    for param_name in cur_node.param_oval:
                        if param_name in commit.param_nval:
                            continue
                        elif param_name in commit.param_oval:
                            if commit.param_oval[param_name] != cur_node.param_oval[param_name]:
                                raise Exception(msg % (
param_name, commit.sha, commit.param_oval[param_name], cur_node.param_oval[param_name]
                                ))
                        else:
                            commit.param_oval[param_name] = cur_node.param_oval[param_name]
                            if commit.sha not in vd_keys_set:
                                stack.append(commit)
                            # if we have visited vd before, it is necessary
                            # to propagate the param, otherwise we do it
                            # in the following iterations of the outer loop
                            elif commit.sha in visited_vd:
                                stack.append(commit)

                i2y -= 1
                if not i2y:
                    yield True
                    i2y = QVD_HP_IBY

    def init_commit_old_val(self, commit, vd):
        # messages for exceptions
        msg1 = "Conflict with param '%s' in commit %s (old_val (%s) != new_val (%s))"
        msg2 = "Conflict with param '%s' in commit %s (old_val (%s) != old_val (%s))"

        for param in vd:
            if param.name in commit.param_nval:
                if commit.param_nval[param.name] != param.old_value:
                    raise Exception(msg1 % (
param.name, commit.sha, param.old_value, commit.param_nval[param.name]
                    ))
            elif param.name in commit.param_oval:
                if commit.param_oval[param.name] != param.old_value:
                    raise Exception(msg2 % (
param.name, commit.sha, param.old_value, commit.param_oval[param.name]
                    ))
            else:
                commit.param_oval[param.name] = param.old_value

    __pygen_deps__ = ("pci_c", "device_tree")

    def __gen_code__(self, gen):
        gen.reset_gen(self)

        gen.gen_field("device_tree = ")
        gen.pprint(self.device_tree)

        gen.gen_field("known_targets = ")
        gen.pprint(self.known_targets)

        gen.gen_field("list_headers = ")
        gen.pprint(self.list_headers)

        gen.gen_field("version_desc = ")
        gen.pprint(self.version_desc)

        gen.gen_field("pci_classes = " + gen.nameof(self.pci_c))

        gen.gen_end()

    # The method made the cache active.
    def use(self):
        self.stc.set_cur_stc()
        PCIId.db = self.pci_c

        previous = QemuVersionCache.current
        QemuVersionCache.current = self
        return previous

class ConfigHost(object):

    def __init__(self, config_host_path):
        with open(config_host_path) as f:
            self.content = f.read()

    def __getattr__(self, parameter):
        return QemuVersionDescription.ch_lookup(self.content, parameter)

class BadBuildPath(ValueError):
    pass

class QVCWasNotInitialized(RuntimeError):
    pass

class QVCIsNotReady(RuntimeError):
    pass

# Iterations Between Yields of Device Tree Macros adding task
QVD_DTM_IBY = 100
# Iterations Between Yields of Heuristic Propagation task
QVD_HP_IBY = 100
# Iterations Between Yields of Check Modified Files task
QVD_CMF_IBY = 100
# Iterations Between Yields of Check Untracked Files task
QVD_CUF_IBY = 100

QVD_QH_HASH = "qh_hash"

class QemuVersionDescription(object):
    current = None
    # Current version of the QVD. Please use notation `u"_v{number}"` for next
    # versions. Increase number manually if current changes affect the QVD.
    version = u"_v2"

    def __init__(self, build_path, version = None):
        config_host_path = join(build_path, "config-host.mak")
        if not isfile(config_host_path):
            raise BadBuildPath("%s does not exists." % config_host_path)
        self.config_host = config_host = ConfigHost(config_host_path)

        self.build_path = build_path
        self.src_path = fixpath(config_host.SRC_PATH)
        self.target_list = config_host.TARGET_DIRS.split(" ")

        self.softmmu_targets = st = set()
        for t in self.target_list:
            target_desc = t.split("-")
            if "softmmu" in target_desc:
                st.add(target_desc[0])

        # Get SHA
        self.repo = Repo(self.src_path)

        if version is None:
            c = self.repo.head.commit
        else:
            c = git_find_commit(self.repo, version)

        self.commit_sha = c.hexsha

        VERSION = c.tree["VERSION"]
        self.qemu_version = VERSION.data_stream.read().strip().decode()

        print("Qemu version is {}".format(self.qemu_version))

        self.qvc = None
        self.qvc_is_ready = False

    @lazy
    def include_paths(self):
        if get_vp("tcg headers prefix") == "tcg/":
            return (
                # path, need recursion
                ("include", True),
            )
        else:
            return (
                # path, need recursion
                ("include", True),
                ("tcg", False)
            )

    @lazy
    def include_abs_paths(self):
        return tuple(join(self.src_path, d) for d, _ in self.include_paths)

    # The method made the description active
    def use(self):
        if self.qvc is None:
            self.init_cache()
        self.qvc.use()

        previous = QemuVersionDescription.current
        QemuVersionDescription.current = self
        return previous

    def init_cache(self):
        callco(self.co_init_cache())

    def forget_cache(self):
        if self.qvc is None:
            raise QVCWasNotInitialized()
        if not self.qvc_is_ready:
            raise QVCIsNotReady(
                "Attempt to forget QVC which is not ready yet."
            )
        self.qvc = None
        self.qvc_is_ready = False

    def remove_cache(self):
        if self.qvc:
            self.qvc = None
            self.qvc_is_ready = False
            remove_file(self.qvc_path)

    @lazy
    def qvc_file_name(self):
        return (u"qvc" + QemuVersionDescription.version + u"_" +
            self.commit_sha + u".py"
        )

    @lazy
    def qvc_path(self):
        return join(self.build_path, self.qvc_file_name)

    def co_init_cache(self):
        if self.qvc is not None:
            print("Multiple QVC initialization " + self.src_path)
            self.qvc = None

        qemu_heuristic_hash = calculate_qh_hash()

        yield True

        if not isfile(self.qvc_path):
            self.qvc = QemuVersionCache()

            # Check out Qemu source to a temporary directory and analyze it
            # there. This avoids problems with user changes in main working
            # directory.

            print("Checking out temporary source tree...")

            # Note. Alternatively, checking out can be performed without
            # cloning. Instead, a magic might be casted on GIT_DIR and
            # GIT_WORK_TREE environment variables. But, this approach resets
            # staged files in src_path repository which can be inconvenient
            # for a user.
            # `fast_repo_clone` relies on external library functions which
            # grab control for a long time. Hence, we should call it in a
            # dedicated process.
            tmp_repo = yield co_process(
                fast_repo_clone,
                self.repo, self.commit_sha, "qdt-qemu"
            )
            tmp_work_dir = tmp_repo.working_tree_dir

            # Qemu source tree analysis is too long process and temporary
            # clone of Qemu is big enough. If the process is terminated, the
            # clone junks file system. Use `Cleaner`, a dedicated process,
            # to remove the clone in that case.
            clean_work_dir_task = get_cleaner().rmtree(tmp_work_dir)

            print("Temporary source tree: %s" % tmp_work_dir)

            # make new QVC active and begin construction
            prev_qvc = self.qvc.use()

            # gen version description
            yield self.qvc.co_computing_parameters(self.repo, self.commit_sha)
            self.qvc.version_desc[QVD_QH_HASH] = qemu_heuristic_hash

            yield True

            # set Qemu version heuristics according to current version
            initialize_version(self.qvc.version_desc)

            yield Header.co_build_inclusions(tmp_work_dir, self.include_paths)

            self.qvc.list_headers = self.qvc.stc.create_header_db()

            yield self.co_gen_known_targets(tmp_work_dir)

            rmtree(tmp_work_dir)
            get_cleaner().cancel(clean_work_dir_task)

            yield self.co_init_device_tree()

            # Search for PCI Ids
            PCIClassification.build()

            yield self.co_overwrite_cache()
        else:
            self.load_cache()
            # make just loaded QVC active
            prev_qvc = self.qvc.use()

            if self.qvc.list_headers is not None:
                yield True

                yield self.qvc.stc.co_load_header_db(self.qvc.list_headers)

            yield True

            # verify that the version_desc is not outdated
            is_outdated = False
            try:
                checksum = self.qvc.version_desc[QVD_QH_HASH]
            except KeyError:
                is_outdated = True
            else:
                if not checksum == qemu_heuristic_hash:
                    is_outdated = True
            if is_outdated:
                yield self.qvc.co_computing_parameters(
                    self.repo,
                    self.commit_sha
                )
                self.qvc.version_desc[QVD_QH_HASH] = qemu_heuristic_hash

            yield True

            # set Qemu version heuristics according to current version
            initialize_version(self.qvc.version_desc)

            dt = self.qvc.device_tree
            if dt:
                # Targets to be added to the cache
                new_targets = self.softmmu_targets - dt.arches
                has_new_target = len(new_targets) > 0
            else:
                new_targets = self.softmmu_targets
                has_new_target = True

            if has_new_target:
                yield self.co_init_device_tree(new_targets)

            if is_outdated or has_new_target:
                yield self.co_overwrite_cache()

        yield True

        # initialize Qemu types in QVC
        get_vp()["qemu types definer"]()
        get_vp()["msi_init type definer"]()

        if prev_qvc is not None:
            prev_qvc.use()

        self.qvc_is_ready = True

    def co_overwrite_cache(self):
        qvc_path = self.qvc_path

        if isfile(qvc_path):
            cleaner = get_cleaner()

            # save backup
            back = qvc_path + ".back"

            rename_replacing(qvc_path, back)
            yield True

            # If user stops the interpreter during `pythonize`...
            revert_task = cleaner.schedule(rename_replacing, back, qvc_path)

            yield True
        else:
            back = None

        try:
            pythonize(self.qvc, qvc_path)
        except:
            if back is not None:
                rename_replacing(back, qvc_path)
            raise
        # A backup is never redundant.
        # else:
        #     if back is not None:
        #         yield True
        #         remove_file(back)
        finally:
            if back is not None:
                cleaner.cancel(revert_task)

    def load_cache(self):
        if not isfile(self.qvc_path):
            raise Exception("%s does not exists." % self.qvc_path)
        else:
            print("Loading QVC from " + self.qvc_path)
            variables = {}
            context = {
                "QemuVersionCache": QemuVersionCache,
                "QVHDict": QVHDict
            }

            import qemu
            context.update(qemu.__dict__)

            execfile(self.qvc_path, context, variables)

            for v in variables.values():
                if isinstance(v, QemuVersionCache):
                    self.qvc = v
                    break
            else:
                raise Exception(
"No QemuVersionCache was loaded from %s." % self.qvc_path
                )
            self.qvc.version_desc = QVHDict(self.qvc.version_desc)

    def co_check_modified_files(self):
        # A diff between the index and the working tree
        modified_files = set()

        # index.diff(None) returns diff between index and working directory
        for e in self.repo.index.diff(None) + self.repo.index.diff('HEAD'):
            abs_path = join(u(self.src_path), e.a_path)
            for include in self.include_abs_paths:
                if abs_path.startswith(include + sep):
                    modified_files.add(abs_path[len(include)+1:])

        yield True

        i2y = QVD_CMF_IBY
        for e in self.qvc.list_headers:
            if e['path'] in modified_files:
                raise ProcessingModifiedFile(e['path'])

            if i2y == 0:
                yield True
                i2y = QVD_CMF_IBY
            else:
                i2y -= 1

    def co_check_untracked_files(self):
        i2y = QVD_CUF_IBY
        for path in self.repo.untracked_files:
            abs_path = join(self.src_path, path)
            for include in self.include_abs_paths:
                if abs_path.startswith(include + sep):
                    raise ProcessingUntrackedFile(path)

                if i2y == 0:
                    yield True
                    i2y = QVD_CUF_IBY
                else:
                    i2y -= 1

    @staticmethod
    def ch_lookup(config_host, parameter):
        # Parameter initialization described as "parameter=value"
        # in config-host.mak and therefore we are looking for "parameter=".
        indx_begin = config_host.find(parameter + "=")
        if indx_begin == -1:
            raise Exception('Parameter "{}" does not exists.'.format(
                parameter
            ))
        indx_end = config_host.find("\n", indx_begin)

        option = config_host[indx_begin:indx_end]
        return option.split("=")[1]

    def co_gen_known_targets(self, work_dir):
        print("Making known targets set...")
        dconfigs = join(work_dir, "default-configs")
        kts = set()
        for config in listdir(dconfigs):
            yield True
            for suffix in ["-softmmu.mak", "-linux-user.mak", "-bsd-user.mak"]:
                if config.endswith(suffix):
                    kts.add(config[:-len(suffix)])
                    break
        print("Known targets set was made")
        self.qvc.known_targets = kts

    def co_init_device_tree(self, targets = None):
        if not targets:
            targets = self.softmmu_targets

        yield True

        print("Creating Device Tree for " +
              ", ".join(t for t in targets) + "..."
        )

        root = self.qvc.device_tree
        if root is None:
            root = QType("device")

        arches_count = len(root.arches)
        for arch in targets:
            # Try to get QOM tree using binaries from different places.
            # Installed binary is tried first because in this case Qemu
            # launched as during normal operation.
            # However, if user did not install Qemu, we should try to use
            # binary from build directory.
            install_dir = join(fixpath(self.config_host.prefix), "bin")
            build_dir = join(self.build_path, arch + "-softmmu")

            binaries = [
                join(install_dir, "qemu-system-" + arch),
                join(build_dir, "qemu-system-" + arch)
            ]

            message = []

            for qemu_exec in binaries:
                try:
                    yield co_update_device_tree(
                        qemu_exec,
                        self.src_path,
                        arch,
                        root
                    )
                except Exception as e:
                    message.extend([
                        "\n",
                        "Failure for binary '%s':\n" % qemu_exec,
                        "\n",
                    ])
                    if isinstance(e, (CancelledCallee, FailedCallee)):
                        message.extend(e.callee.traceback_lines)
                    else:
                        message.extend(format_exception(*exc_info()))
                else:
                    root.arches.add(arch)
                    # Stop on first successful update.
                    break
            else:
                # All binaries are absent/useless.
                message.insert(0, "Device Tree for %s isn't created:\n" % arch)
                print("".join(message))

        if not root.children:
            # Device Tree was not built
            self.qvc.device_tree = None
            return

        if arches_count == len(root.arches):
            # No new architecture has been added
            return

        self.qvc.device_tree = root
        print("Device Tree was created")

        t2m = defaultdict(list)
        yield self.co_text2macros(t2m)

        print("Adding macros to device tree ...")
        yield self.co_add_dt_macro(self.qvc.device_tree.children, t2m)
        print("Macros were added to device tree")

    def co_text2macros(self, text2macros):
        """
            Creates text-to-macros `text2macros` dictionary.

        text2macros
            dictionary with list default value
        """

        # iterations to yield
        i2y = QVD_DTM_IBY
        print("Building text to macros mapping...")

        for t in self.qvc.stc.reg_type.values():
            if i2y == 0:
                yield True
                i2y = QVD_DTM_IBY
            else:
                i2y -= 1

            if isinstance(t, Macro):
                text2macros[t.text].append(t.name)

        print("The mapping was built")

    def co_add_dt_macro(self, dt, text2macros):
        # iterations to yield
        i2y = QVD_DTM_IBY

        # Use the mapping to build "list_dt"
        for qt in dt.values():
            if i2y == 0:
                yield True
                i2y = QVD_DTM_IBY
            else:
                i2y -= 1

            dt_type = qt.name
            dt_type_text = '"' + dt_type + '"'

            if dt_type_text in text2macros:
                macros = text2macros[dt_type_text]
                if qt.macros:
                    if set(macros) - set(qt.macros):
                        print("Override macros for type %s (%r vs %r)" % (
                            dt_type_text, qt.macros, macros
                        ))
                qt.macros = list(macros)

            yield self.co_add_dt_macro(qt.children, text2macros)
