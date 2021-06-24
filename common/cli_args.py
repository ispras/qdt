__all__ = [
    "iter_dict_as_args"
  , "arg_list"
  , "iter_dict_as_configure_args"
  , "configure_arg_list"
]


def iter_dict_as_args(d, long_arg_prefix = "-"):
    def arg(a):
        a = str(a)
        if len(a) > 1:
            return long_arg_prefix + a
        else:
            return "-" + a

    for a, v in d.items():
        if v is None:
            continue
        if v is False:
            yield arg("no-" + str(a))
        elif v is True:
            yield arg(a)
        elif isinstance(v, (list, tuple, set)):
            for sub_v in v:
                yield arg(a)
                yield str(sub_v)
        else:
            yield arg(a)
            yield str(v)


def arg_list(container, **kw):
    if isinstance(container, dict):
        ret = list(iter_dict_as_args(container, **kw))
    else:
        ret = list(container)
    return ret


def iter_dict_as_configure_args(d):
    for a, v in d.items():
        if v is None:
            yield "--" + str(a)
        if v is False:
            yield "--disable-" + str(a)
        elif v is True:
            yield "--enable-" + str(a)
        elif isinstance(v, (list, tuple, set)):
            yield "--" + str(a) + "=" + ",".join(v)
        else:
            yield "--" + str(a) + "=" + str(v)


def configure_arg_list(container):
    if isinstance(container, dict):
        return list(iter_dict_as_configure_args(container))
    else:
        return list(container)
