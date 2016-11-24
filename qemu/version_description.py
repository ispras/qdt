from source import \
    SourceTreeContainer, \
    Header, \
    Type, \
    Macro, \
    add_base_types

from predefined_types import \
    add_types

from common import \
    PyGenerator

from json import load

from subprocess import \
    check_output, \
    STDOUT

import os

bp_file_name = "build_path_list"

qvd_reg = {}

def load_build_path_list():
    if not os.path.isfile(bp_file_name):
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
    if not os.path.isfile(bp_file_name):
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
    if qvd_reg[path] == None:
        qvd_reg[path] = QemuVersionDescription(path)
    else:
        raise Exception("Multiple Qemu version descriptions for %s." % path)

def qvd_get(path):
    if not path in qvd_reg.keys():
        qvd_create(path)

    return qvd_reg[path]

def qvd_get_registered(path):
    if not path in qvd_reg.keys():
        raise Exception("%s was not registered." % path)

    return qvd_reg[path]

def qvds_load():
    for k, v in qvd_reg.iteritems():
        if v == None:
            qvd_reg[k] = QemuVersionDescription(k)

def qvds_load_with_cache():
    for k, v in qvd_reg.iteritems():
        if v == None:
            qvd_reg[k] = QemuVersionDescription(k)
        qvd = qvd_reg[k]
        qvd.init_cache()

def qvds_init_cache():
    for v in qvd_reg.values():
        if not v == None:
            v.init_cache()

class QemuVersionCache(object):
    def __init__(self,
                 list_headers = None,
                 device_tree = None):
        self.device_tree = device_tree

        # Create source tree container
        self.stc = SourceTreeContainer()
        # Temporarily
        self.stc.set_cur_stc()

        if not list_headers == None:
            add_base_types()
            self.stc.load_header_db(list_headers)

    def __children__(self):
        return []

    def __gen_code__(self, gen):
        gen.reset_gen(self)

        gen.gen_field("device_tree = ")
        gen.pprint(self.device_tree)

        list_headers = self.stc.create_header_db()
        gen.gen_field("list_headers = ")
        gen.pprint(list_headers)

        gen.gen_end()

class QemuVersionDescription(object):
    def __init__(self, build_path):
        config_host_path = os.path.join(build_path, 'config-host.mak')
        if not os.path.isfile(config_host_path):
            forget_build_path(build_path)
            raise Exception("%s does not exists." % config_host_path)

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
        self.commit_sha = QemuVersionDescription.get_head_commit_sha(
            self.src_path
        )

        self.qvc = None

    def init_cache(self):
        if not self.qvc == None:
            raise Exception("Multiple cache init (source: %s)" % self.src_path)

        qvc_file_name = "qvc_" + self.commit_sha + ".py"
        qvc_path = os.path.join(self.build_path, qvc_file_name)

        if not os.path.isfile(qvc_path):
            self.qvc = QemuVersionCache()
            QemuVersionDescription.gen_header_inclusion(
                self.src_path,
                self.qvc.stc
            )
            self.qvc.device_tree = QemuVersionDescription.gen_device_tree(
                self.build_path,
                self.qvc.stc
            )
            PyGenerator().serialize(open(qvc_path, "wb"), self.qvc)
        else:
            self.load_cache(qvc_path)

    def load_cache(self, qvc_path):
        if not os.path.isfile(qvc_path):
            raise Exception("%s does not exists." % qvc_path)
        else:
            print("Loading QVC from " + qvc_path)
            QemuVersionDescription.check_uncommit_change(self.src_path)
            variables = {}
            context = {
                "QemuVersionCache": QemuVersionCache
            }
            execfile(qvc_path, context, variables)

            for v in variables.values():
                if isinstance(v, QemuVersionCache):
                    self.qvc = v
                    break
                else:
                    raise Exception(
"No QemuVersionCache was loaded from %s." % qvc_path
                    )

    @staticmethod
    def get_head_commit_sha(src_path):
        cmd = ['git', '-C', src_path, 'rev-parse', 'HEAD']
        sha = check_output(cmd, stderr = STDOUT)

        sha = sha.rstrip()

        # Error when get SHA
        if not (sha.islower() and sha.isalnum() and len(sha) == 40):
            raise Exception('Geg SHA: "{}".'.format(sha))

        return sha

    @staticmethod
    def check_uncommit_change(src_path):
        cmd = ['git', '-C', src_path, 'status']
        status = check_output(cmd, stderr = STDOUT)
        if "fatal" in status:
            raise Exception("%s: %s" % (src_path, status))

        if "Changes to be committed" in status:
            print "WARNING! " + \
                  src_path + " has changes that need to be committed."

        if "Changes not staged for commit" in status:
            print "WARNING! " + src_path + ": changes not staged for commit."

        if "Untracked files" in status:
            print "WARNING! " + src_path + " has untracked files."

    @staticmethod
    def compare_by_sha(sha):
        # git rev-list --count SHA
        pass

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

    @staticmethod
    def gen_header_inclusion(src_path, stc):
        include_path = os.path.join(src_path, 'include')
        print("Building Qemu header inclusion tree")
        add_base_types()
        stc.build_inclusions(include_path)
        add_types(stc)

    # TODO: get dt from qemu
    @staticmethod
    def gen_device_tree(build_path, stc):
        dt_db_fname = build_path + "/dt.json"
        if os.path.isfile(dt_db_fname):
            print("Loading Device Tree from " + dt_db_fname)
            dt_db_reader = open(dt_db_fname, "rb")
            device_tree = load(dt_db_reader)
            dt_db_reader.close()
            print("Adding macros to " + dt_db_fname)
            QemuVersionDescription.add_dt_macro(device_tree, stc)
            return device_tree
        else:
            return None

    @staticmethod
    def add_dt_macro(list_dt, stc):
        for dict_dt in list_dt:
            dt_type = dict_dt["type"]
            for h in stc.reg_header.values():
                for t in h.types.values():
                    if isinstance(t, Macro):
                        if t.text == '"' + dt_type + '"':
                            if "macro" in dict_dt:
                                if not t.name in dict_dt["macro"]:
                                    dict_dt["macro"].append(t.name)
                            else:
                                dict_dt["macro"] = [t.name]
            if "property" in dict_dt:
                for dt_property in dict_dt["property"]:
                    dt_property_name = dt_property["name"]
                    for h in stc.reg_header.values():
                        for t in h.types.values():
                            if isinstance(t, Macro):
                                if t.text == '"' + dt_property_name + '"':
                                    if "macro" in dt_property:
                                        if not t.name in dt_property["macro"]:
                                            dt_property["macro"].append(t.name)
                                    else:
                                        dt_property["macro"] = [t.name]
            if "children" in dict_dt:
                QemuVersionDescription.add_dt_macro(dict_dt["children"], stc)
