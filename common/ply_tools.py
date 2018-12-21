__all__ = [
    "gen_tokens"
]

def gen_tokens(glob):
    "Given global scope yielding PLY tokens."
    for g in list(glob):
        if g.startswith("t_"):
            name = g[2:]
            if name in ("error", "ignore"):
                continue
            yield name
