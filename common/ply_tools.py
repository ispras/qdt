__all__ = [
    "gen_tokens"
  , "def_tokens"
]

def gen_tokens(glob):
    "Given global scope yielding PLY tokens."
    for g in list(glob):
        if g.startswith("t_"):
            name = g[2:]
            if name in ("error", "ignore"):
                continue
            yield name

def def_tokens(glob):
    glob["tokens"] = tuple(gen_tokens(glob))
