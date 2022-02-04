__all__ = [
    "show_stats"
]


from common import (
    mlget as _,
)
from rr3.stat import (
    RR3Stat,
)

from argparse import (
    ArgumentParser,
)
from csv import (
    DictReader,
)
from matplotlib.pyplot import (
    plot,
    rcParams,
    figure,
    xticks,
    yticks,
    grid,
    gca,
    show,
    legend,
)
from matplotlib.ticker import (
    StrMethodFormatter,
)
from randomcolor import (
    RandomColor,
)
from os.path import (
    splitext,
    commonprefix,
    dirname,
)
from warnings import (
    filterwarnings,
)

class PlotRandomColor(RandomColor):

    def set_format(self, hsv, format_):
        # format_ is defined by the algorithm below (for matplotlib.plot)
        r, g, b = self.hsv_to_rgb(hsv)
        return r / 255., g / 255., b / 255., 1.


def main():
    ap = ArgumentParser(
        description = "Record/Replay #3 Statistics Analyzer",
    )
    arg = ap.add_argument

    arg("rtstat",
        nargs = '+',
    )
    arg("--color-seed",
        default = 0xDEADBEEF,
        type = int,
    )

    args = ap.parse_args()
    show_stats(args.rtstat,
        color_seed = args.color_seed
    )


def iter_dash_variants():
    yield (1, 0)
    yield (1, 1)

    parts = [(1, 1)]
    parts_gen = iter_dash_parts()
    parts.append(next(parts_gen))
    parts.append(next(parts_gen))

    parts_2_take = 1
    while True:
        for s in iter_N_of_K(parts_2_take, len(parts) - 1):
            dash = parts[-1]
            for i in s:
                dash += parts[i]
            yield dash

        parts_2_take += 1
        parts.append(next(parts_gen))


def iter_N_of_K(N, K):
    if N == 1:
        for i in range(K):
            yield (i,)
    else:
        for i in range(0, K - N):
            for tail in iter_N_of_K(N - 1, K - 1 - i):
                tail = tuple((t + i + 1) for t in tail)
                yield (i,) + tail


def iter_dash_parts():
    i = 2
    while True:
        yield (i, 1)
        i <<= 1


def show_stats(rtstat, color_seed = 0xDEADBEEF, color = None, dashes = True):
    if len(rtstat) > 1:
        prefix_len = len(commonprefix(rtstat))
    else:
        prefix_len = len(dirname(rtstat[0])) + 1

    stats = []

    for file_name in rtstat:
        with open(file_name, "r") as f:
            r = DictReader(f,
                delimiter = ';',
                skipinitialspace = True,
                strict = True,
            )
            name = splitext(file_name[prefix_len:])[0]
            stats.append(RR3Stat(list(r), name = name))


    if color is None:
        colorgen = PlotRandomColor(seed = color_seed)
        colors = colorgen.generate(count = len(stats))
    else:
        def iter_color():
            while True:
                yield color
        colors = iter_color()

    if dashes:
        dash_var_iter = iter_dash_variants()
    else:
        def dash_var_iter():
            while True:
                yield (1, 0)
        dash_var_iter = dash_var_iter()

    figure(figsize = (16, 10), dpi = 80)

    for stat, color, dashes in zip(stats, colors, dash_var_iter):
        plot(
            stat.row("total_instructions"),
            stat.row("time"),
            color = color,
            label = stat.name,
            dashes = dashes,
        )

    # Generic parametrs
    filterwarnings(action = 'once')

    large = 22
    med = 16
    small = 12
    params = {
        'axes.titlesize': large,
        'legend.fontsize': med,
        'figure.figsize': (16, small),
        'axes.labelsize': med,
        'axes.titlesize': med,
        'xtick.labelsize': med,
        'ytick.labelsize': med,
        'figure.titlesize': large,
    }
    rcParams.update(params)

    # Decoration
    xticks(
        rotation = 0,
        fontsize = small,
        horizontalalignment = 'center',
        alpha = .7,
    )
    yticks(
        fontsize = small,
        alpha = .7,
    )
    grid(
        axis = 'both',
        alpha = .3,
    )

    # Remove borders
    ax = gca()
    ax.set(
        ylabel = _("Time [seconds]").get(),
        xlabel = _("Total Instructions").get(),
    )
    ax.spines["top"].set_alpha(0.0)
    ax.spines["bottom"].set_alpha(0.3)
    ax.spines["right"].set_alpha(0.0)
    ax.spines["left"].set_alpha(0.3)
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,}"))
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,}"))

    legend()

    show()


if __name__ == "__main__":
    exit(main() or 0)
