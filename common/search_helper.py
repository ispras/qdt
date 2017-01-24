def co_find_eq(iterable, **request):
    for i in iterable:
        for attr, val in request.iteritems():
            try:
                if getattr(i, attr) != val:
                    break
            except AttributeError:
                break
        else:
            yield i

    raise StopIteration()
