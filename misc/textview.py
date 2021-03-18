from argparse import (
    ArgumentParser,
)
from common import (
    UserSettings,
)
from widgets import (
    TextViewerWindow,
)


class QDTTextViewSettings(UserSettings):

    _suffix = ".qdt_textview_settings.py"

    def __init__(self):
        super(QDTTextViewSettings, self).__init__(
            glob = globals(),
            version = 0.1,
            # default values
            geometry = (600, 800),
        )


def main():
    ap = ArgumentParser(
        description = "A Text Viewer",
    )
    ap.add_argument("file_name")

    args = ap.parse_args()

    w = TextViewerWindow()
    w.file_name = args.file_name

    with QDTTextViewSettings() as settings:
        w.set_geometry_delayed(*settings.geometry)

        w.mainloop()

        # only save width and height
        settings.geometry = w.last_geometry[:2]


if __name__ == "__main__":
    exit(main() or 0)
