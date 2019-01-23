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

        def gitcmd(*cmd):
            p = Popen(cmd, cwd = tmp_wc, stderr = PIPE, stdout = PIPE)

            p.wait()

            if p.returncode:
                raise RuntimeError(
                    "Git command failed %u\nstdout:\n%s\nstderr:\n%s\n" % (
                        p.returncode, p.stdout.read(),
                        p.stderr.read()
                    )
                )

            return p

        for cmd in [
            ["git", "clone", "-n", "-s", self.path, "."],
            ["git", "checkout", "-f", version],
        ]:
            gitcmd(*cmd)

        # redirect submodule URLs to local caches inside repository
        status = gitcmd("git", "submodule", "status", "--recursive")

        submodules = []
        for l in status.stdout.readlines():
            # format: "-SHA1 dir"
            submodules.append(l.rstrip().split(' ')[1])

        if submodules:
            for sm in submodules:
                # https://stackoverflow.com/a/30675130/7623015
                gitcmd("git", "config", "--file=.gitmodules",
                    "submodule." + sm + ".url",
                    join(self.path, ".git", "modules", sm)
                )

            gitcmd("git", "submodule", "update", "--init", "--recursive")

        return tmp_wc

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


M = Measurement


def project_measurements(qdtgit, qemugit, ctx, commit_list, qproject, qp_path,
    m_count = 5,
    env = "python2"
):
    if m_count < 1:
        return

    machine = uname()

    qvc = "qvc_%s.py" % qemugit.repo.commit(qproject.target_version).hexsha

    print("Checking Qemu out...")
    qemuwc = qemugit.get_tmp_wc(qproject.target_version, "qemu")
    tmp_build = mkdtemp(prefix = "qemu-%s-build-" % qproject.target_version)

    print("Configuring Qemu...")
    configure = Popen(
        [
            join(qemugit.path, "configure"),
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

    for sha1 in commit_list:
        print("Checking QDT out (%s)..." % sha1)
        qdtwc = qdtgit.get_tmp_wc(sha1, "qdt")

        for i in range(m_count):
            print("Measuring...\n\n")

            qdt_cwd = mkdtemp(prefix = "qdt-cwd-")

            if i > 0:
                # restore cache
                copyfile(join(qdtwc, qvc), join(tmp_build, qvc))

            t0 = time()
            proc = Popen(
                [
                    join(qdtwc, "qemu_device_creator.py"),
                    "-b", tmp_build,
                    "-t", qproject.target_version,
                    qp_path
                ],
                cwd = qdt_cwd
            )
            proc.wait()
            t1 = time()

            if i == 0:
                # preserve cache
                copyfile(join(tmp_build, qvc), join(qdtwc, qvc))

            total = t1 - t0

            print("\n\ntotal: %s\n\n" % total)

            ctx.mes.setdefault(sha1, []).append(M(
                i = i,
                time = total,
                returncode = proc.returncode,
                env = env,
                machine = machine
            ))

            rmtree(qdt_cwd)

            # restore qemu src and build from backup
            rmtree(tmp_build)
            rmtree(qemuwc)
            copytree(join(q_back, "src"), qemuwc)
            copytree(join(q_back, "build"), tmp_build)

            if proc.returncode:
                break

        ctx._save()

        rmtree(qdtwc)

    rmtree(tmp_build)
    rmtree(qemuwc)
    rmtree(q_back)


def tox_measurements(gitrepo, ctx, commit_list, m_count = 5, env = "py27"):
    if m_count < 1:
        return

    machine = uname()

    for sha1 in commit_list:
        print("Measuring %s\n\n" % sha1)

        wc = gitrepo.get_tmp_wc(sha1)

        tox_prepare = Popen(["tox", "-e", env, "--notest"], cwd = wc)
        tox_prepare.wait()

        print("\n\n...\n\n")

        for i in range(m_count):
            t0 = time()
            tox = Popen(["tox", "-e", env], cwd = wc)
            tox.wait()
            t1 = time()

            total = t1 - t0

            print("\n\ntotal: %s\n\n" % total)

            ctx.mes.setdefault(sha1, []).append(M(
                i = i,
                time = total,
                returncode = tox.returncode,
                env = env,
                machine = machine
            ))

            if tox.returncode:
                break

        ctx._save()

        rmtree(wc)


def accuracy(err):
    digits = 0
    while int(err) == 0:
        digits += 1
        err *= 10.0
    return digits


def plot_measurements(repo, ctx, commit_seq):
    xcoords = []
    ycoords = []
    yerr = []
    commits = []

    cur_machine = uname()

    mes = ctx.mes

    for x, sha1 in enumerate(commit_seq):
        xmes = []
        for i, t, res, env, machine in mes.get(sha1, []):
            if machine != cur_machine:
                # TODO: different plot (graph)
                continue
            if env != "python2":
                # TODO: different line (errorbar) with annotations on the plot
                continue
            if res: # failed, do not show
                continue
            if i == 0: # cache building, too long
                continue

            xmes.append(t)

        _sum = 0.0
        _len = 0

        for t in xmes:
            _len += 1
            _sum += t

        if _len == 0:
            _avg = 0
        else:
            _avg = _sum / _len

        _err = 0

        for t in xmes:
            _err += (t - _avg) ** 2

        if _len == 0:
            _err = 0
        else:
            _err /= _len

        if _err < 0:
            t_fmt = "%%.%uf" % accuracy(_err)
        else:
            t_fmt = "%f"

        commits.append((
                "%s\n%s--\nlaunches = %u, avg. t = " + t_fmt + " sec, err = "
                +t_fmt + " sec"
            ) % (
                sha1, repo.commit(sha1).message, _len, _avg, _err
            )
        )
        xcoords.append(x)
        ycoords.append(_avg)

        yerr.append(_err)

    # def sort(x):
    #     print(x)
    #     return x[0]

    # xcoords, ycoords, yerr, commits =  zip(*sorted(
    #     zip(xcoords, ycoords, yerr, commits),
    #     key = sort
    # ))

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

    ebar = plt.errorbar(xcoords, ycoords, yerr = yerr)
    ebar.lines[0].set_pickradius(15)

    def update_annot(ind):
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

        # ebar.lines Tuple of (data_line, caplines, barlinecols).
        cont, ind = ebar.lines[0].contains(e)
        if cont:
            update_annot(ind)
            annot.set_visible(True)
            fig.canvas.draw_idle()
        elif vis:
            annot.set_visible(False)
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", hover)

    plt.grid()
    plt.show()


class CommitsTestResults(Persistent):

    def __init__(self):
        super(CommitsTestResults, self).__init__("_commits_test_results.py",
            glob = globals()
        )

    @lazy
    def mes(self):
        return {}


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
        nargs='?',
        default = "HEAD",
        metavar = "<current-tree-ish>",
        help = "branch to test"
    )
    ap.add_argument("base",
        nargs='?',
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
        ))

        project_measurements(qdtgit, qemugit, c, commit_list, project, script,
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
