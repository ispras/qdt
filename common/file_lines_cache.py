__all__ = [
    "FileLinesCache",
]


class FileLinesCache(dict):

    def __missing__(self, path):
        with open(path, "r") as f:
            text = f.read()
        self[path] = lines = text.splitlines(False)
        return lines
