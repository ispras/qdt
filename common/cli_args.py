__all__ = [
    "iter_dict_as_args"
  , "arg_list"
]


def iter_dict_as_args(d):
    for a, v in d.items():
        if v is None:
            continue
        if v is False:
            yield "-no-" + str(a)
        elif v is True:
            yield "-" + str(a)
        elif isinstance(v, (list, tuple, set)):
            for sub_v in v:
                yield "-" + str(a)
                yield str(sub_v)
        else:
            yield "-" + str(a)
            yield str(v)


def arg_list(container):
    if isinstance(container, dict):
        ret = list(iter_dict_as_args(container))
    else:
        ret = list(container)
    return ret
