__all__ = [
    "pipeline"
  , "co_pipeline"
  , "pipeline_iter"
  , "limit_stage"
]


def pipeline(*stages):
    # Startup.
    for stage in stages:
        if next(stage) is not None:
            raise ValueError("%s does not follow pipeline protocol" % stage)

    while True:
        # Input to first stage is always `None`.
        # I.e. it must be an actual input producer.
        # Other stages are never given `None` as input.
        intermediate = None

        for stage in stages:
            try:
                intermediate = stage.send(intermediate)
            except StopIteration:
                # Normal end of work.
                return

            if intermediate is None:
                break
        else:
            yield intermediate


def co_pipeline(*stages):
    "A pipeline for `CoDispatcher`."
    for _ in pipeline(*stages):
        # Output of last stage is always ignored in CoDispatcher task mode.
        # I.e. last stage must be an actual output consumer.

        # The pipeline always can proceed.
        yield True


def pipeline_iter(iterable):
    "An `iter` analog for co_pipeline*."

    if (yield) is not None:
        raise RuntimeError(
            "pipeline_iter must be used as a FIRST stage of pipeline"
        )

    for item in iter(iterable):
        yield item
        # We actually should check `yield` returned `None` like above.
        # But it's too expensive for fool protection.


def limit_stage(limit):
    "Interrupts pipeline after `limit` items passing."
    res = yield
    while limit > 0:
        res = yield res
        limit -= 1
