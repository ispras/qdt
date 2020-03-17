__all__ = [
    "pipeline"
  , "co_pipeline"
  , "limit_stage"
]


def pipeline(*stages):
    """ A stage is a coroutine. It's input is returned by `yield`.
It's output is `yield` argument. If next output requires extra input
it can just `yield` (`None`). Output of last stage is pipeline output.
    First stage is never `send`-ed input: any standard iterator can
be used. Rest stages are never `send`-ed `None`.
    """

    if not stages:
        return

    # Just started generator cannot receive an input. Hence, intermediate
    # stages are prohibited to output something at startup. They are
    # executed until first `yield` to become ready for first input.
    for stage in stages[1:-1]:
        if next(stage) is not None:
            raise ValueError("%s does not follow pipeline protocol" % stage)

    first_output = next(stages[-1])
    if first_output is not None:
        # Last stage is ready at startup without any input.
        yield first_output

    siter = iter(stages)

    while True:
        stage = next(siter)
        try:
            intermediate = next(stage)
        except StopIteration:
            # Normal end of work (no more input).
            return

        for stage in siter:
            try:
                intermediate = stage.send(intermediate)
            except StopIteration:
                # Normal end of work (a stage will not consume more
                # input).
                return

            if intermediate is None:
                # Current stage is not ready. Extra data are required.
                break
        else:
            # Last stage yielded a value.
            yield intermediate

        # Propagate new data from pipeline beginning.
        siter = iter(stages)


def co_pipeline(*stages):
    "A pipeline for `CoDispatcher`."
    for _ in pipeline(*stages):
        # Output of last stage is always ignored in CoDispatcher task mode.
        # I.e. last stage must be an actual output consumer.

        # The pipeline always can proceed.
        yield True


def limit_stage(limit):
    "Interrupts pipeline after `limit` items passing."
    res = yield
    while limit > 0:
        res = yield res
        limit -= 1
