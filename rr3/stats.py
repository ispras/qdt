__all__ = [
    "show_stats"
]


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


def show_stats(rtstat, color_seed = 0xDEADBEEF):
    prefix_len = len(commonprefix(rtstat))

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

    colorgen = PlotRandomColor(seed = color_seed)

    figure(figsize = (16, 10), dpi = 80)

    for stat, color in zip(stats, colorgen.generate(count = len(stats))):
        plot(
            stat.row("total_instructions"),
            stat.row("time"),
            color = color,
            label = stat.name,
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
    ax.set(ylabel = "Time [seconds]", xlabel = "Total Instructions")
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
