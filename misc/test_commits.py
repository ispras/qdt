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
    uname,
    Measurer,
    fast_repo_clone,
    ee,
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
from contextlib import (
    contextmanager
)
from math import (
    sqrt
)


TC_PRINT_COMMANDS = ee("TC_PRINT_COMMANDS")
TC_MELD = not ee("TC_NO_MELD")
TC_PRINT_STARTUP_ENVIRONMENT = ee("TC_PRINT_STARTUP_ENVIRONMENT")


TEST_STARTUP_ENV = dict(environ)
# Test environment is built basing on testing environment.
# But some Python-related variables breaks operation of the tool being tested.
for var in ["PYTHONPATH"]:
    try:
        del TEST_STARTUP_ENV[var]
    except:
        pass # no variable - no problem

if TC_PRINT_STARTUP_ENVIRONMENT:
    print("\n".join(("%s=%s" % i) for i in TEST_STARTUP_ENV.items()))


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
        yield self.test_time
        yield self.test_returncode

    # default values for previous versions

    @lazy
    def cache_ready(self):
        return True

    @lazy
    def differences(self):
        return False

    @lazy
    def test_time(self):
        return None

    @lazy
    def test_returncode(self):
        return None


M = Measurement

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

        _len = len(self.mes)

        if _len == 0:
            _avg = 0
            _err = 0
        else:
            # median filtering with a window size 3 and looped edges
            mes = [self.mes[-1]] + self.mes + [self.mes[0]]
            smes = [None] * _len
            for i in range(0, _len):
                smes[i] = sorted(mes[i:i + 3])[1]

            _avg = sum(smes) / _len

            _err = 0
            for t in smes:
                _err += (t - _avg) ** 2
            _err = sqrt(_err / _len)

        t_fmt = "%%.%uf" % accuracy(_err)

        self.commits.append((
            "%s\n%s--\nlaunches = %u, " +
            "avg. t = " + t_fmt + " sec, " +
            "err = " + t_fmt + " sec"
        ) % (
            sha1, message, _len, _avg, _err
        ))

        self.xcoords.append(x)
        self.ycoords.append(_avg)

        self.yerr.append(_err)

        self.mes = []


def plot_measurements(repo, ctx, commit_seq):
    plots = defaultdict(Plot)

    cur_machine = uname()

    mes = ctx.mes

    for x, sha1 in enumerate(commit_seq):
        for _, t, res, env, machine, cache_ready, _, _ in mes.get(sha1, []):
            if machine != cur_machine:
                # TODO: different plot (graph)
                continue
            if res: # failed, do not show
                continue

            plots[env].mes.append(t)

        # Graph for tests
        for _, _, _, env, machine, _, t, res in mes.get(sha1, []):
            if machine != cur_machine:
                # TODO: different plot (graph)
                continue
            if res: # failed, do not show
                continue

            plots[env + " (tests)"].mes.append(t)

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


class QDTMeasurer(Measurer):

    def __init__(self, repo, current, base, project, project_path,
        caches = None,
        diffs = join(".", "proj_mes_diffs")
    ):
        """
:param caches:
    Path to directory with existing QVCs. Use it iff QVC building
    algorithm testing is not required.
        """
        super(QDTMeasurer, self).__init__(repo, current, base)

        self.qdtgit = repo
        self.clone_prefix = "qdt"

        qvd = qvd_get(project.build_path, version = project.target_version)

        self.qproject = project
        self.qemugit = qemugit = Repo(qvd.src_path)
        self.qp_path = project_path
        self.caches = caches

        # generated code will be saved as a patch
        diffs = join(abspath(diffs), datetime.now().strftime("%Y%m%d-%H%M%S"))
        if not isdir(diffs):
            makedirs(diffs)

        self.diffs = diffs

        self.qvc = "qvc_%s.py" % qemugit.commit(project.target_version).hexsha

    def __enter__(self):
        print("Checking Qemu out...")
        self.qemuwc = qemuwc = fast_repo_clone(self.qemugit,
            version = self.qproject.target_version,
            prefix = "qemu"
        )

        # `fast_repo_clone` changes `.gitmodules` file. This change is not
        # required for consequent operation. So, revert it to avoid junk in
        # diff files.
        qemuwc.git.reset("HEAD", hard = True)

        self.tmp_build = tmp_build = mkdtemp(
            prefix = "qemu-%s-build-" % self.qproject.target_version
        )

        print("Configuring Qemu...")
        configure = Popen(
            [
                join(qemuwc.working_tree_dir, "configure"),
                "--target-list=" + ",".join(["x86_64-softmmu"])
            ],
            env = dict(TEST_STARTUP_ENV),
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
        self.q_back = q_back = mkdtemp(
            prefix = "qemu-%s-back-" % self.qproject.target_version
        )

        copytree(qemuwc.working_tree_dir, join(q_back, "src"))
        copytree(tmp_build, join(q_back, "build"))

        self.prev_diff = None

        return self

    def __exit__(self, *_):
        rmtree(self.tmp_build)
        rmtree(self.qemuwc.working_tree_dir)
        rmtree(self.q_back)

    @contextmanager
    def __environment__(self, ctx):
        print("Testing for environment '%s'" % ctx.env_name)

        # Prepare working directory for launches
        self.qdt_cwd = qdt_cwd = mkdtemp(prefix = "qdt-cwd-")

        # Launch QDC for generating LALR tables of PLY.
        cmds = [
            ctx.interpreter,
            join(ctx.clone.working_tree_dir, "qemu_device_creator.py"),
            "--help"
        ]

        if TC_PRINT_COMMANDS:
            print(" ".join(cmds))

        Popen(cmds, cwd = qdt_cwd, env = dict(TEST_STARTUP_ENV)).wait()

        if ctx.caches is not None and join(ctx.caches, ctx.qvc):
            # use existing cache
            ctx.qv_cache = join(ctx.caches, ctx.qvc)
        else:
            ctx.qv_cache = None

        try:
            yield self
        finally:
            rmtree(qdt_cwd)

    @contextmanager
    def __launch__(self, ctx):
        # no pre-launch preparations
        try:
            yield self
        finally:
            # restore Qemu source and build directories from backup
            rmtree(ctx.tmp_build)
            rmtree(ctx.qemuwc.working_tree_dir)
            copytree(join(ctx.q_back, "src"), ctx.qemuwc.working_tree_dir)
            copytree(join(ctx.q_back, "build"), ctx.tmp_build)

    def __measure__(self, ctx):
        yield "machine", ctx.machine
        yield "env", ctx.env_name
        yield "i", ctx.launch_number

        print("Preparing CWD...")

        qv_cache = ctx.qv_cache

        if qv_cache:
            # restore cache
            copyfile(
                qv_cache,
                join(ctx.tmp_build, ctx.qvc)
            )
            yield "cache_ready", True
        else:
            yield "cache_ready", False

        print("Measuring...")
        cmds = [
            ctx.interpreter,
            join(ctx.clone.working_tree_dir, "qemu_device_creator.py"),
            "-b", ctx.tmp_build,
            "-t", ctx.qproject.target_version,
            ctx.qp_path
        ]

        if TC_PRINT_COMMANDS:
            print(" ".join(cmds))

        t0 = time()
        proc = Popen(cmds, cwd = self.qdt_cwd, env = dict(TEST_STARTUP_ENV))
        proc.wait()
        t1 = time()

        total = t1 - t0

        print("\ntotal: %s\n" % total)

        yield "returncode", proc.returncode
        yield "time", total

        if proc.returncode:
            ctx.break_request = True
            ctx.errors = True

            if not TC_PRINT_COMMANDS:
                # always print commands for bad runs
                print("Command was:")
                print(" ".join(cmds))

        if qv_cache is None:
            # preserve cache
            qv_cache = join(ctx.clone.working_tree_dir, ctx.qvc)
            copyfile(join(ctx.tmp_build, ctx.qvc), qv_cache)
            ctx.qv_cache = qv_cache

        print("Running test...")

        test_cmds = [
            ctx.interpreter,
            "-m", "unittest",
            "test"
        ]

        if TC_PRINT_COMMANDS:
            print(" ".join(test_cmds))

        t0 = time()
        test_proc = Popen(test_cmds,
            cwd = ctx.clone.working_tree_dir,
            env = dict(TEST_STARTUP_ENV)
        )
        test_proc.wait()
        t1 = time()
        test_total = t1 - t0

        print("\ntotal: %s\n" % test_total)

        yield "test_returncode", test_proc.returncode
        yield "test_time", test_total

        if test_proc.returncode:
            ctx.break_request = True
            ctx.errors = True

            if not TC_PRINT_COMMANDS:
                print("Test launch command was:")
                print(" ".join(test_cmds))

        # save patch
        diff = join(ctx.diffs, "%u-%s-for-%s-under-%s-%u.patch" % (
            ctx.commit_number, ctx.sha1, ctx.qproject.target_version,
            ctx.env_name, ctx.launch_number
        ))

        ctx.qemuwc.git.add("-A")
        with open(diff, "w") as diff_stream:
            diff_str = ctx.qemuwc.git.diff(cached = True)
            diff_stream.write(diff_str)

        # check if patches are different
        prev_diff = ctx.prev_diff
        if prev_diff is not None and not cmp(prev_diff, diff):
            print("Changes to Qemu are different.")

            p_diff = Popen(["diff", prev_diff, diff],
                env = dict(TEST_STARTUP_ENV),
                stdout = PIPE,
                stderr = PIPE,
            )
            out = p_diff.communicate()[0]
            with open(diff + ".diff", "wb") as f:
                f.write(out)

            if TC_MELD:
                Popen(["meld", prev_diff, diff],
                    env = dict(TEST_STARTUP_ENV),
                    stdout = PIPE,
                    stderr = PIPE,
                    stdin = PIPE
                )

            yield "differences", True
        else:
            yield "differences", False

        ctx.prev_diff = diff

    def __account_dict__(self, ctx, **res):
        # remember results
        self.results.mes.setdefault(ctx.sha1, []).append(M(
            **dict(res)
        ))

        self.results._save()


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

    repo = Repo(args.repo)

    measurer = QDTMeasurer(repo, args.current, args.base, project, script,
        caches = project.build_path
    )

    with CommitsTestResults() as results:
        measurer.results = results
        measurer.measure(m_count = args.measurements)

        # TODO
        # tox_measurements(repo, c, commit_list,
        #     m_count = args.measurements
        # )
        plot_measurements(repo, results, measurer.commit_queue)

    return 0


if __name__ == "__main__":
    exit(main())
