from git import (
    Repo
)
from tempfile import (
    mkdtemp
)
from subprocess import (
    PIPE,
    Popen
)
from os.path import (
    join,
    isfile,
    isdir,
    abspath,
    dirname
)
from shutil import (
    copyfile,
    copytree,
    rmtree
)
from time import (
    time
)
from matplotlib import (
    pyplot as plt
)
from common import (
    execfile,
    lazy,
    Persistent,
    Extensible
)
from argparse import (
    ArgumentTypeError,
    ArgumentParser,
    ArgumentDefaultsHelpFormatter
)
from platform import (
    uname
)
import qdt
from traceback import (
    print_exc
)
from qemu import (
    qvd_get
)
from os import (
    makedirs,
    environ
)
from datetime import (
    datetime
)
from filecmp import (
    cmp
)
from collections import (
    defaultdict
)


class GitWC(str):
    "Working copy"

    def __new__(cls, path, producer):
        res = str.__new__(cls, path)
        res.producer = producer
        return res

    def __str__(self):
        return self.path

    def cmd(self, *cmd, **kw):
        p = Popen(cmd, cwd = self, stderr = PIPE, stdout = PIPE, **kw)

        p.wait()

        if p.returncode:
            raise RuntimeError(
                "Git command failed %u\nstdout:\n%s\nstderr:\n%s\n" % (
                    p.returncode, p.stdout.read(),
                    p.stderr.read()
                )
            )

        return p


class GitHelper(object):

    def __init__(self, path):
        self.path = path
        self.repo = Repo(path)

    @property
    def head(self):
        return self.repo.head.commit.hexsha

    def version(self, tree_ish):
        return self.repo.commit(tree_ish).hexsha

    def get_tmp_wc(self, version = None, prefix = "repo"):
        if version is None:
            version = self.head
        else:
            version = self.version(version)

        tmp_wc = mkdtemp(prefix = "%s-%s-" % (prefix, version))
        wc = GitWC(tmp_wc, self)

        for cmd in [
            ["git", "clone", "-n", "-s", self.path, "."],
            ["git", "checkout", "-f", version],
        ]:
            wc.cmd(*cmd)

        # redirect submodule URLs to local caches inside main repository
        status = wc.cmd("git", "submodule", "status", "--recursive")

        submodules = []
        for l in status.stdout.readlines():
            # format: "-SHA1 dir"
            submodules.append(l.rstrip().split(' ')[1])

        if submodules:
            for sm in submodules:
                # https://stackoverflow.com/a/30675130/7623015
                wc.cmd("git", "config", "--file=.gitmodules",
                    "submodule." + sm + ".url",
                    join(self.path, ".git", "modules", sm)
                )

            wc.cmd("git", "submodule", "update", "--init", "--recursive")

        return wc

    def commits(self, tree_ish, early_tree_ish = None):
        version = self.version(tree_ish)
        if early_tree_ish is None:
            early = None
        else:
            early = self.version(early_tree_ish)

        log = self.repo.git.rev_list(early + ".." + version)
        for l in log.split("\n"):
            yield l.strip()


class Measurement(Extensible):

    def __var_base__(self):
        return "m"

    def __iter__(self):
        yield self.i
        yield self.time
        yield self.returncode
        yield self.env
        yield self.machine
        yield self.cache_ready

    # default values for previous versions

    @lazy
    def cache_ready(self):
        return True

    @lazy
    def differences(self):
        return False


M = Measurement

ENVS = dict(
    py2 = dict(
        interpreter = "python2"
    ),
    py3 = dict(
        interpreter = "python3"
    )
)


def project_measurements(qdtgit, qemugit, ctx, commit_list, qproject, qp_path,
    caches = None,
    m_count = 5,
    envs = ("py3", "py2"),
    diffs = join(".", "proj_mes_diffs")
):
    """
    :param caches:
        Path to directory with existing QVCs. Use it iff QVC building
        algorithm testing is not required.
    """

    if m_count < 1:
        return

    # generated code will be saved as a patch
    diffs = join(abspath(diffs), datetime.now().strftime("%Y%m%d-%H%M%S"))
    if not isdir(diffs):
        makedirs(diffs)

    machine = uname()

    qvc = "qvc_%s.py" % qemugit.repo.commit(qproject.target_version).hexsha

    print("Checking Qemu out...")
    qemuwc = qemugit.get_tmp_wc(qproject.target_version, "qemu")
    tmp_build = mkdtemp(prefix = "qemu-%s-build-" % qproject.target_version)

    print("Configuring Qemu...")
    configure = Popen(
        [
            join(qemuwc, "configure"),
            "--target-list=" + ",".join(["x86_64-softmmu"])
        ],
        cwd = tmp_build,
        stderr = PIPE,
        stdout = PIPE
    )
    configure.wait()
    if configure.returncode:
        raise RuntimeError(
            "Qemu configuration failed %u\nstdout:\n%s\nstderr:\n%s\n" % (
                configure.returncode, configure.stdout.read(),
                configure.stderr.read()
            )
        )

    print("Backing Qemu configuration...")
    q_back = mkdtemp(prefix = "qemu-%s-back-" % qproject.target_version)

    copytree(qemuwc, join(q_back, "src"))
    copytree(tmp_build, join(q_back, "build"))

    prev_diff = None

    for t, sha1 in enumerate(commit_list):
        print("Checking QDT out (%s)...\n%s" % (
            sha1,
            "\n".join((("> " + l) if l else ">") for l in
                qdtgit.repo.commit(sha1).message.splitlines()
            )
        ))
        qdtwc = qdtgit.get_tmp_wc(sha1, "qdt")

        errors = False

        for env in envs:
            print("Testing for environment '%s'" % env)

            for i in range(m_count):
                print("Preparing CWD...")

                qdt_cwd = mkdtemp(prefix = "qdt-cwd-")

                cache_ready = False
                if i > 0:
                    # restore cache
                    copyfile(join(qdtwc, qvc), join(tmp_build, qvc))
                    cache_ready = True
                elif caches is not None and isfile(join(caches, qvc)):
                    # use existing cache
                    copyfile(join(caches, qvc), join(tmp_build, qvc))
                    cache_ready = True

                print("Measuring...")

                cmds = [
                    ENVS[env]["interpreter"],
                    join(qdtwc, "qemu_device_creator.py"),
                    "-b", tmp_build,
                    "-t", qproject.target_version,
                    qp_path
                ]

                if environ.get("TC_PRINT_COMMANDS", "0") == "1":
                    print(" ".join(cmds))

                t0 = time()
                proc = Popen(cmds, cwd = qdt_cwd, env = {})
                proc.wait()
                t1 = time()

                total = t1 - t0

                print("\ntotal: %s\n" % total)

                if i == 0:
                    # preserve cache
                    copyfile(join(tmp_build, qvc), join(qdtwc, qvc))

                rmtree(qdt_cwd)

                # save patch
                diff = join(diffs, "%u-%s-for-%s-under-%s-%u.patch" % (
                    t, sha1, qproject.target_version, env, i
                ))

                qemuwc.cmd("git", "add", "-A")
                qemuwc.cmd("git diff --cached > " + diff, shell = True)

                # check if patches are different
                differences = False

                if prev_diff is not None:
                    if not cmp(prev_diff, diff):
                        print("Changes to Qemu are different.")
                        differences = True

                        p_diff = Popen(["diff", prev_diff, diff],
                            stdout = PIPE,
                            stderr = PIPE,
                        )
                        out = p_diff.communicate()[0]
                        with open(diff + ".diff", "w") as f:
                            f.write(out)

                        if environ.get("TC_NO_MELD", "0") != "1":
                            Popen(["meld", prev_diff, diff],
                                stdout = PIPE,
                                stderr = PIPE,
                                stdin = PIPE
                            )

                prev_diff = diff

                # remember results
                ctx.mes.setdefault(sha1, []).append(M(
                    i = i,
                    time = total,
                    returncode = proc.returncode,
                    env = env,
                    machine = machine,
                    cache_ready = cache_ready,
                    differences = differences
                ))

                ctx._save()

                # restore qemu src and build from backup
                rmtree(tmp_build)
                rmtree(qemuwc)
                copytree(join(q_back, "src"), qemuwc)
                copytree(join(q_back, "build"), tmp_build)

                if proc.returncode:
                    errors = True

                    if environ.get("TC_PRINT_COMMANDS", "0") != "1":
                        # always print commands for bad runs
                        print("Command was:")
                        print(" ".join(cmds))
                    break

        if not errors:
            # allow user to work with bad version
            rmtree(qdtwc)

    rmtree(tmp_build)
    rmtree(qemuwc)
    rmtree(q_back)


def accuracy(err):
    if err <= 0 or 1.0 <= err:
        return 0
    digits = 0
    while int(err) == 0:
        digits += 1
        err *= 10.0
    return digits


class Plot(object):

    def __init__(self):
        self.mes = []
        self.xcoords = []
        self.ycoords = []
        self.yerr = []
        self.commits = []

    def _commit(self, x, sha1, message):
        while len(self.xcoords) < x - 1:
            # handle skipped measurements
            self.xcoords.append(len(self.xcoords))
            self.ycoords.append(0)
            self.yerr.append(0)
            self.commits.append("-")

        _sum = 0.0
        _len = 0

        for t in self.mes:
            _len += 1
            _sum += t

        if _len == 0:
            _avg = 0
        else:
            _avg = _sum / _len

        _err = 0

        for t in self.mes:
            _err += (t - _avg) ** 2

        if _len == 0:
            _err = 0
        else:
            _err /= _len

        t_fmt = "%%.%uf" % accuracy(_err)

        self.commits.append((
                "%s\n%s--\nlaunches = %u, avg. t = " + t_fmt + " sec, err = "
                +t_fmt + " sec"
            ) % (
                sha1, message, _len, _avg, _err
            )
        )

        self.xcoords.append(x)
        self.ycoords.append(_avg)

        self.yerr.append(_err)

        self.mes = []


def plot_measurements(repo, ctx, commit_seq):
    plots = defaultdict(Plot)

    cur_machine = uname()

    mes = ctx.mes

    for x, sha1 in enumerate(commit_seq):
        for _, t, res, env, machine, cache_ready in mes.get(sha1, []):
            if machine != cur_machine:
                # TODO: different plot (graph)
                continue
            if res: # failed, do not show
                continue
            if not cache_ready: # cache building, too long
                continue

            plots[env].mes.append(t)

        for plot in plots.values():
            plot._commit(x, sha1, repo.commit(sha1).message)

    fig, ax = plt.subplots()

    # https://stackoverflow.com/questions/7908636/possible-to-make-labels-appear-when-hovering-over-a-point-in-matplotlib
    # But, an alternative annotation layout is implemented which avoids moving
    # of the text beyond figure
    annot = ax.annotate("",
        xy = (0, 0),
        xycoords = "figure pixels",
        bbox = dict(boxstyle = "round", fc = "w"),
        arrowprops = dict(arrowstyle = "->")
    )
    annot.set_visible(False)

    ax.set_xlim(-1, max(max(p.xcoords or [0]) for p in plots.values()) + 1)

    for env, plot in plots.items():
        ebar = plt.errorbar(plot.xcoords, plot.ycoords,
            yerr = plot.yerr,
            label = env
        )
        ebar.lines[0].set_pickradius(15)
        plot.ebar = ebar

    def update_annot(ind, ebar, commits):
        x = ind["ind"][0]
        pos = ebar.lines[0].get_xydata()[x]

        bbox_patch = annot.get_bbox_patch()

        fsize = fig.get_size_inches() * fig.dpi

        # screen coords in pixels
        sx, sy = ax.transData.transform(pos)

        # text offset
        T_OFF = 20
        tx, ty = sx + T_OFF, sy + T_OFF

        if tx + bbox_patch.get_width() > fsize[0]:
            # fitting in figure
            shift = bbox_patch.get_width() + 2 * T_OFF
            if shift < tx: # mirror
                tx -= shift
            else: # align by figure border
                tx = fsize[0] - bbox_patch.get_width() - T_OFF

        if ty + bbox_patch.get_height() > fsize[1]:
            shift = bbox_patch.get_height() + 2 * T_OFF
            if shift < ty:
                ty -= shift
            else:
                ty = fsize[1] - bbox_patch.get_height() - T_OFF

        annot.set_position((tx, ty))
        annot.xy = (sx, sy)

        annot.set_text(commits[x])
        bbox_patch.set_alpha(0.4)

    def hover(e):
        vis = annot.get_visible()
        if e.inaxes != ax:
            return

        for plot in plots.values():
            ebar = plot.ebar
            # ebar.lines Tuple of (data_line, caplines, barlinecols).
            cont, ind = ebar.lines[0].contains(e)
            if cont:
                update_annot(ind, ebar, plot.commits)
                annot.set_visible(True)
                fig.canvas.draw_idle()
            elif vis:
                annot.set_visible(False)
                fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", hover)

    ax.legend(loc = "best")

    plt.grid()
    plt.show()


class CommitsTestResults(Persistent):

    def __init__(self):
        super(CommitsTestResults, self).__init__("_commits_test_results.py",
            glob = globals(),
            version = 1.1,
            mes = {}
        )

    def __update__(self, loaded_version):
        if loaded_version == 1.0:
            for mess in self.mes.values():
                for m in mess:
                    if m.env == "python2":
                        m.env = "py2"
        else:
            raise ValueError("Unsupported loaded version %s" % loaded_version)


class default(str):
    """ Unique string. Used to distinguish a default CLI argument value and a
user provided value which is equal to default. They are different objects in
Python.
    """


def arg_type_directory(string):
    if not isdir(string):
        raise ArgumentTypeError(
            "'%s' is not a directory" % string)
    return string


def arg_type_file(string):
    if not isfile(string):
        raise ArgumentTypeError(
            "'%s' is not a file" % string)
    return string


def main():
    ap = ArgumentParser(
        description = "Test helper fot a Git branch.",
        formatter_class = ArgumentDefaultsHelpFormatter
    )
    ap.add_argument("-r", "--repo",
        default = abspath(dirname(dirname(__file__))),
        type = arg_type_directory,
        metavar = "dir",
        help = "repository location"
    )
    ap.add_argument("-m", "--measurements",
        default = 3,
        type = int,
        metavar = "count",
        help = "measurements count, 0 (to only view previous results)"
    )
    ap.add_argument("-s", "--script",
        default = "project.py",
        type = arg_type_file,
        metavar = "file.py",
        help = "a script containing definition of a project to generate"
    )
    ap.add_argument("-b", "--qemu-build",
        default = default("."),
        type = arg_type_directory,
        metavar = "dir",
        help = "override QEMU build path of the project"
    )
    ap.add_argument("-t", "--target-version",
        default = default("master"),
        metavar = "<tree-ish>", # like in Git's docs
        help = "assume given version of Qemu"
        " (overrides project's target_version)"
    )
    ap.add_argument("current",
        nargs = '?',
        default = "HEAD",
        metavar = "<current-tree-ish>",
        help = "branch to test"
    )
    ap.add_argument("base",
        nargs = '?',
        default = "master",
        metavar = "<base-tree-ish>",
        help = "base version"
    )

    args = ap.parse_args()

    # TODO: outline QProject loading from qemu_device_creator.py
    script = abspath(args.script)

    loaded = {}
    try:
        execfile(script, dict(qdt.__dict__), loaded)
    except:
        print("Cannot load configuration from '%s'" % script)
        print_exc()
        return -1

    for v in loaded.values():
        if isinstance(v, qdt.QProject):
            project = v
            break
    else:
        print("Script '%s' does not define a project to generate." % script)
        return -1

    if (    not isinstance(args.qemu_build, default)
         or not getattr(project, "build_path", None)
    ):
        project.build_path = args.qemu_build

    if (    not isinstance(args.target_version, default)
         or not getattr(project, "target_version", None)
    ):
        project.target_version = args.target_version

    qdtgit = GitHelper(args.repo)

    qvd = qvd_get(project.build_path, version = project.target_version)

    qemugit = GitHelper(qvd.src_path)

    with CommitsTestResults() as c:
        commit_list = tuple(reversed(
            list(qdtgit.commits(args.current, early_tree_ish = args.base))
            +[qdtgit.repo.commit(args.base).hexsha]
        ))

        project_measurements(qdtgit, qemugit, c, commit_list, project, script,
            caches = project.build_path,
            m_count = args.measurements,
        )

        # TODO
        # tox_measurements(repo, c, commit_list,
        #     m_count = args.measurements
        # )
        plot_measurements(qdtgit.repo, c, commit_list)

    return 0


if __name__ == "__main__":
    exit(main())
