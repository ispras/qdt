from source import \
    SourceTreeContainer, \
    Header, \
    Macro

from common import \
    callco, \
    remove_file, \
    execfile, \
    PyGenerator

from json import \
    load

from subprocess import \
    Popen, \
    PIPE, \
    check_output, \
    STDOUT

from .version import \
    QVHDict, \
    initialize_version, \
    qemu_heuristic_db, \
    calculate_qh_hash, \
    get_vp

from os.path import \
    join, \
    isfile

from .pci_ids import \
    PCIId, \
    PCIClassification

from git import \
    Repo

bp_file_name = "build_path_list"

qvd_reg = {}

def load_build_path_list():
    if not isfile(bp_file_name):
        return

    build_path_f = open(bp_file_name)
    build_path_list = build_path_f.readlines()
    build_path_f.close()
    for val in build_path_list:
        v = val.rstrip()
        qvd_reg[v] = None

def account_build_path(path):
    if path in qvd_reg.keys():
        return
    if not isfile(bp_file_name):
        f = open(bp_file_name, 'w')
    else:
        f = open(bp_file_name, 'a')

    f.write(path + "\n")
    f.close()

    qvd_reg[path] = None

def forget_build_path(path):
    if not path in qvd_reg.keys():
        raise Exception("%s is not registered." % path)

    del qvd_reg[path]

    f = open(bp_file_name, 'w')
    for val in qvd_reg.keys():
        f.write(val + "\n")
    f.close()

def qvd_create(path):
    account_build_path(path)

    qvd = qvd_reg[path]

    if qvd == None:
        qvd = QemuVersionDescription(path)
    else:
        raise Exception("Multiple Qemu version descriptions for %s." % path)

    qvd_reg[path] = qvd
    return qvd

def qvd_get(path):
    try:
        qvd = qvd_reg[path]
    except KeyError:
        qvd = None

    if qvd is None:
        qvd = qvd_create(path)

    return qvd

def qvd_get_registered(path):
    if not path in qvd_reg.keys():
        raise Exception("%s was not registered." % path)

    return qvd_get(path)

def qvds_load():
    for k, v in qvd_reg.items():
        if v == None:
            qvd_reg[k] = QemuVersionDescription(k)

def qvd_load_with_cache(build_path):
    qvd = qvd_get(build_path)
    qvd.init_cache()
    return qvd

def qvds_load_with_cache():
    for k, v in qvd_reg.items():
        if v == None:
            qvd_reg[k] = QemuVersionDescription(k)
        qvd = qvd_reg[k]
        qvd.init_cache()

def qvds_init_cache():
    for v in qvd_reg.values():
        if not v == None:
            v.init_cache()

class CommitDesc(object):
    def __init__(self, sha, parents, children):
        self.sha = sha
        self.parents = parents
        self.children = children

        # dict of QEMUVersionParameterDescription new_value parameters
        self.param_nval = {}
        # dict of QEMUVersionParameterDescription old_value parameters
        self.param_oval = {}

        # serial number according to the topological sorting
        self.num = None

class QemuVersionCache(object):
    current = None

    def __init__(self,
                 list_headers = None,
                 device_tree = None,
                 version_desc = None,
                 pci_classes = None
    ):
        self.device_tree = device_tree
        self.list_headers = list_headers
        self.version_desc = version_desc

        # Create source tree container
        self.stc = SourceTreeContainer()
        self.pci_c = PCIClassification() if pci_classes is None else pci_classes

    def co_computing_parameters(self, repo):
        print("Creating graph of commit's description ...")
        yield self.co_gen_commits_graph(repo)
        print("Graph of commit's description was created")

        yield self.co_propagate_param()

        c = self.commit_desc_nodes[repo.head.commit.hexsha]
        param = self.version_desc = QVHDict()
        for k, v in c.param_nval.items():
            param[k] = v
        for k, v in c.param_oval.items():
            param[k] = v

    def co_propagate_param(self):
        vd = qemu_heuristic_db
        vd_list = []
        for k in vd.keys():
            if k in self.commit_desc_nodes:
                vd_list.append((k, self.commit_desc_nodes[k].num))

        sorted_tuple = sorted(vd_list, key = lambda x: x[1])
        sorted_vd_keys = [t[0] for t in sorted_tuple]

        yield True

        # first, need to propagate the new labels
        print("Propagation params in graph of commit's description ...")
        yield self.co_propagate_new_param(sorted_vd_keys, vd)
        yield self.co_propagate_old_param(sorted_vd_keys, vd)
        print("Params in graph of commit's description were propagated")

    def co_gen_commits_graph(self, repo):
        iterations_per_yield = 20
        commit_desc_nodes = {}
        # n is serial number according to the topology sorting
        n = 0
        # to_enum is used during topological sorting
        # it contains commit to enumerate
        to_enum = None
        # build_stack contains eges represented by tuples
        # (parent, child), where parent is instance of
        # git.Commit, child is instance of CommitDesc
        build_stack = []
        for head in repo.branches:
            # skip processed heads
            if head.commit.hexsha in commit_desc_nodes:
                continue

            head_desc = CommitDesc(head.commit.hexsha, [], [])
            commit_desc_nodes[head.commit.hexsha] = head_desc
            # add edges connected to head being processed
            for p in head.commit.parents:
                build_stack.append((p, head_desc))

            while build_stack:
                parent, child_commit_desc = build_stack.pop()

                try:
                    parent_desc = commit_desc_nodes[parent.hexsha]
                except KeyError:
                    parent_desc = CommitDesc(parent.hexsha, [], [])
                    commit_desc_nodes[parent.hexsha] = parent_desc

                    if parent.parents:
                        for p in parent.parents:
                            build_stack.append((p, parent_desc))
                    else:
                        # current edge parent is an elder commit in the tree,
                        # that is why we should enumerate starting from it
                        to_enum = parent_desc
                else:
                    # the existence of parent_desc means that parent has been
                    # enumerated before. Hence, we starts enumeration from
                    # it's child
                    to_enum = child_commit_desc
                finally:
                    parent_desc.children.append(child_commit_desc)
                    child_commit_desc.parents.append(parent_desc)

                # numbering is performed from the 'to_enum' to either a leaf
                # commit or a commit just before a merge which have at least
                # one parent without number (except the commit)
                while to_enum is not None:
                    e = to_enum
                    to_enum = None
                    # if the number of parents in the commit_desc_nodes
                    # is equal to the number of parents in the repo,
                    # then all parents were numbered (added) earlier
                    # according to the graph building algorithm,
                    # else we cannot assign number to the commit yet
                    if len(e.parents) == len(repo.commit(e.sha).parents):
                        e.num = n
                        n = n + 1
                        # according to the algorithm, only one child
                        # have no number. Other children either have
                        # been enumerated already or are not added yet
                        for c in e.children:
                            if c.num is None:
                                to_enum = c
                                break

                    if n % iterations_per_yield == 0:
                        yield True

            if len(commit_desc_nodes) % iterations_per_yield == 0:
                yield True

        self.commit_desc_nodes = commit_desc_nodes

    def co_propagate_new_param(self, sorted_vd_keys, vd):
        '''This method propagate QEMUVersionParameterDescription.new_value
        in graph of commits. It must be called before old_value propagation.

        sorted_vd_keys: keys of qemu_heuristic_db sorted in ascending order
        by num of CommitDesc. It's necessary to optimize the graph traversal.
        vd: qemu_heuristic_db
        '''

        for key in sorted_vd_keys:
            cur_vd = vd[key]
            cur_node = self.commit_desc_nodes[key]
            for vpd in cur_vd:
                cur_node.param_nval[vpd.name] = vpd.new_value

        yield True

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

                yield True

    def co_propagate_old_param(self, sorted_vd_keys, vd):
        '''This method propagate QEMUVersionParameterDescription.old_value
        in graph of commits. It must be called after new_value propagation.

        sorted_vd_keys: keys of qemu_heuristic_db sorted in ascending order
        by num of CommitDesc. It's necessary to optimize the graph traversal.
        vd: qemu_heuristic_db
        '''

        # messages for exceptions
        msg1 = "Conflict with param '%s' in commit %s (old_val (%s) != new_val (%s))"
        msg2 = "Conflict with param '%s' in commit %s (old_val (%s) != old_val (%s))"

        # starting initialization
        for key in sorted_vd_keys[::-1]:
            node = self.commit_desc_nodes[key]
            cur_vd = vd[key]
            for parent in node.parents:
                # propagate old_val from node to their parents
                # this is necessary if the vd are consecutive
                for param_name in node.param_oval:
                    parent.param_oval[param_name] = node.param_oval[param_name]
                # init old_val of nodes that consist of vd's parents
                # and check conflicts
                for param in cur_vd:
                    if param.name in parent.param_nval:
                        if parent.param_nval[param.name] != param.old_value:
                            Exception(msg1 % (
param.name, parent.sha, param.old_value, parent.param_nval[param.name]
                            ))
                    elif param.name in parent.param_oval:
                        if param.old_value != parent.param_oval[param.name]:
                            Exception(msg2 % (
param.name, parent.sha, param.old_value, parent.param_oval[param.name]
                            ))
                    else:
                        parent.param_oval[param.name] = param.old_value

        yield True

        # set is used to accelerate propagation
        vd_keys_set = set(sorted_vd_keys)
        visited_vd = set()
        for key in sorted_vd_keys[::-1]:
            stack = []
            # used to avoid multiple processing of one node
            visited_nodes = set([key])
            visited_vd.add(key)
            for p in self.commit_desc_nodes[key].parents:
                stack.append(p)
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
                                Exception(msg2 % (
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

                yield True

    def __children__(self):
        return [ self.pci_c ]

    def __gen_code__(self, gen):
        gen.reset_gen(self)

        gen.gen_field("device_tree = ")
        gen.pprint(self.device_tree)

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

class BadBuildPath(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class MultipleQVCInitialization(Exception):
    def __init__(self, path):
        Exception.__init__(self, path)

class QVCWasNotInitialized(Exception):
    pass

class QVCIsNotReady(Exception):
    pass

# Iterations Between Yields of Device Tree Macros adding task
QVD_DTM_IBY = 100

class QemuVersionDescription(object):
    current = None

    def __init__(self, build_path):
        config_host_path = join(build_path, 'config-host.mak')
        if not isfile(config_host_path):
            forget_build_path(build_path)
            raise BadBuildPath("%s does not exists." % config_host_path)

        self.build_path = build_path

        config_host_f = open(config_host_path)
        config_host = config_host_f.read()
        config_host_f.close()

        self.src_path = QemuVersionDescription.ch_lookup(
            config_host,
            "SRC_PATH"
        )
        self.target_list = QemuVersionDescription.ch_lookup(
            config_host,
            "TARGET_DIRS"
        )

        # Get SHA
        self.repo = Repo(self.src_path)
        self.commit_sha = self.repo.head.commit.hexsha

        VERSION_path = join(self.src_path, 'VERSION')

        if not  isfile(VERSION_path):
            raise BadBuildPath("{} does not exists\n".format(VERSION_path))

        VERSION_f = open(VERSION_path)
        self.qemu_version = VERSION_f.readline().rstrip("\n")
        VERSION_f.close()

        print("Qemu version is {}".format(self.qemu_version))

        self.include_paths = [
            join(self.src_path, 'include'),
            join(self.src_path, 'tcg')
        ]

        self.qvc = None
        self.qvc_is_ready = False

    # The method made the description active
    def use(self):
        if self.qvc == None:
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

    def co_init_cache(self):
        if not self.qvc == None:
            raise MultipleQVCInitialization(self.src_path)

        qvc_file_name = u"qvc_" + self.commit_sha + u".py"
        qvc_path = self.qvc_path = join(self.build_path, qvc_file_name)

        qemu_heuristic_hash = calculate_qh_hash()

        yield True

        if not isfile(qvc_path):
            self.qvc = QemuVersionCache()

            # make new QVC active and begin construction
            prev_qvc = self.qvc.use()
            for path in self.include_paths:
                yield Header.co_build_inclusions(path)

            self.qvc.list_headers = self.qvc.stc.create_header_db()

            yield True

            yield self.co_gen_device_tree()

            # gen version description
            yield self.qvc.co_computing_parameters(self.repo)
            self.qvc.version_desc["qh_hash"] = qemu_heuristic_hash

            # Search for PCI Ids
            PCIClassification.build()

            yield True

            PyGenerator().serialize(open(qvc_path, "wb"), self.qvc)
        else:
            self.load_cache()
            # make just loaded QVC active
            prev_qvc = self.qvc.use()

            if self.qvc.list_headers is not None:
                yield True

                self.qvc.stc.load_header_db(self.qvc.list_headers)

            yield True

            # verify that the version_desc is not outdated
            is_outdated = False
            try:
                checksum = self.qvc.version_desc["qh_hash"]
            except KeyError:
                is_outdated = True
            else:
                if not checksum == qemu_heuristic_hash:
                    is_outdated = True
            if is_outdated:
                remove_file(qvc_path)
                yield self.qvc.co_computing_parameters(self.repo)
                self.qvc.version_desc["qh_hash"] = qemu_heuristic_hash
                PyGenerator().serialize(open(qvc_path, "wb"), self.qvc)

        yield True

        # set Qemu version heuristics according to current version
        initialize_version(self.qvc.version_desc)

        yield True

        # initialize Qemu types in QVC
        get_vp()["qemu types definer"]()
        get_vp()["msi_init type definer"]()

        if prev_qvc is not None:
            prev_qvc.use()

        self.qvc_is_ready = True

    def load_cache(self):
        if not isfile(self.qvc_path):
            raise Exception("%s does not exists." % self.qvc_path)
        else:
            print("Loading QVC from " + self.qvc_path)
            QemuVersionDescription.check_uncommit_change(self.src_path)
            variables = {}
            context = {
                "QemuVersionCache": QemuVersionCache
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

    @staticmethod
    def check_uncommit_change(src_path):
        cmd = ['git', '-C', src_path, 'status']
        p = Popen(cmd, stderr = PIPE, stdout = PIPE)
        p.wait()
        if p.returncode:
            raise Exception("`git status` failed with code %d" % p.returncode)

        """ TODO: either set up corresponding locale settings before command or
use another way to check this.
        """
        """
        if "Changes to be committed" in status:
            print("WARNING! " + \
                  src_path + " has changes that need to be committed.")

        if "Changes not staged for commit" in status:
            print("WARNING! " + src_path + ": changes not staged for commit.")

        if "Untracked files" in status:
            print("WARNING! " + src_path + " has untracked files.")
        """

    @staticmethod
    def ch_lookup(config_host, parameter):
        indx_begin = config_host.find(parameter)
        if indx_begin == -1:
            raise Exception('Parameter "{}" does not exists.'.format(
                parameter
            ))
        indx_end = config_host.find("\n", indx_begin)

        option = config_host[indx_begin:indx_end]
        l = option.split("=")
        if len(l) > 1:
            return l[1]
        else:
            return None

    # TODO: get dt from qemu

    def co_gen_device_tree(self):
        dt_db_fname = join(self.build_path, "dt.json")
        if  isfile(dt_db_fname):
            print("Loading Device Tree from " + dt_db_fname + "...")
            dt_db_reader = open(dt_db_fname, "r")
            self.qvc.device_tree = load(dt_db_reader)
            dt_db_reader.close()
            print("Device Tree was loaded from " + dt_db_fname)
            yield True

            print("Adding macros to device tree ...")
            yield self.co_add_dt_macro(self.qvc.device_tree)
            print("Macros were added to device tree")
        else:
            self.qvc.device_tree = None

    def co_add_dt_macro(self, list_dt, text2macros = None):
        # iterations to yield
        i2y = QVD_DTM_IBY

        if text2macros is None:
            print("Building text to macros mapping...")

            text2macros = {}
            for t in self.qvc.stc.reg_type.values():
                if i2y == 0:
                    yield True
                    i2y = QVD_DTM_IBY
                else:
                    i2y -= 1

                if not isinstance(t, Macro):
                    continue

                text = t.text
                try:
                    aliases = text2macros[text]
                except KeyError:
                    text2macros[text] = [t.name]
                else:
                    aliases.append(t.name)

            print("The mapping was built.")

        # Use the mapping to build "list_dt"
        for dict_dt in list_dt:
            if i2y == 0:
                yield True
                i2y = QVD_DTM_IBY
            else:
                i2y -= 1

            dt_type = dict_dt["type"]
            dt_type_text = '"' + dt_type + '"'
            try:
                aliases = text2macros[dt_type_text]
            except KeyError:
                # No macros for this type
                if "macro" in dict_dt:
                    print(
"No macros for type %s now, removing previous cache..." % dt_type_text
                    )
                    del dict_dt["macro"]
            else:
                if "macro" in dict_dt:
                    print("Override macros for type %s" % dt_type_text)
                dict_dt["macro"] = list(aliases)

            try:
                dt_properties = dict_dt["property"]
            except KeyError:
                pass # QOM type have no properties
            else:
                for dt_property in dt_properties:
                    if i2y == 0:
                        yield True
                        i2y = QVD_DTM_IBY
                    else:
                        i2y -= 1

                    dt_property_name_text = '"' + dt_property["name"] + '"'
                    try:
                        aliases = text2macros[dt_property_name_text]
                    except KeyError:
                        # No macros for this property
                        if "macro" in dt_property:
                            print(
"No macros for property %s of type %s, removing previous cache..." % (
    dt_property_name_text, dt_type_text
)
                            )
                            del dt_property["macro"]
                        continue
                    if "macro" in dt_property:
                        print("Override macros for property %s of type %s" % (
                            dt_property_name_text, dt_type_text
                        ))
                    dt_property["macro"] = list(aliases)

            if "children" in dict_dt:
                yield self.co_add_dt_macro(dict_dt["children"], text2macros)
