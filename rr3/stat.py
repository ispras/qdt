from collections import (
    defaultdict,
)

class RR3Stat(object):

    def __init__(self, list_of_dicts,
        name = None
    ):
        self.list_of_dicts = list_of_dicts
        self.name = name

        totals = defaultdict(lambda : 0.)

        for d in self.list_of_dicts:
            for k, v in tuple(d.items()):
                d[k] = v = float(v)
                if k == "time":
                    continue

                total_k = "total_" + k
                total_v = totals[total_k] + v
                totals[total_k] = total_v
                d[total_k] = total_v

    def row(self, name):
        return list(self.iter_row(name))

    def iter_row(self, name):
        for d in self.list_of_dicts:
            yield d[name]
