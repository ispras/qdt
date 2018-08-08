__all__ = [
    "SourcePosition",
    "Breakpoint",
]

from common import (
    notifier
)


class SourcePosition(object):

    def __init__(self,
        function_name = None,
        line_number = None,
        file_path = None,
        **compat # forward compatibility
    ):
        self.compat = compat

        self.file_path, self.line_number, self.function_name = (
            file_path, line_number, function_name
        )

    def __identify__(self, dia):
        """ This function is called when a debug information becomes available.

        :param dia:
            is a `DWARFInfoAccelerator` instance
        """
        file_path, line_number, function_name = (
            self.file_path, self.line_number, self.function_name
        )

        if function_name is None:
            if file_path is None or line_number is None:
                raise ValueError("To few data to identify a position.")
            """TODO: Given file:line look the corresponding function up or
            raise the ValueError."""
            line_map = dia.find_line_map(file_path)
            line_descs = line_map[line_number]
            self.addresses = tuple(d.state.address for d in line_descs)
        else:
            if line_number is None:
                "TODO: get first line of function"
            else:
                "XXX: check if line is within the function"
            if file_path is None:
                "TODO: get file containing the function"
                "XXX: check if only one file containing the function"
            else:
                "XXX: check if the file containing the function"
            self.addresses = tuple()

        self.file_path, self.line_number, self.function_name = (
            file_path, line_number, function_name
        )


@notifier("happened")
class Breakpoint(object):
    """ The breakpoint handling is split onto two halves (like IRQ handling in
Linux). The `__top_half__` and the `__bottom_half__`. First one is being called
while the process is stopped on the breakpoint. It can fetch actual
short-living runtime information. It should not perform expensive computing
because it slows the process down. That work is for the `__bottom_half__`. The
last one can fetch long-living data from the process but be warned the it is
likely running simultaneously.
    """

    def __init__(self,
        position,
        description,
        *compat, **kompat # forward compatibility
    ):
        """
        :position:
            Instance of `SourcePosition`
        """
        self.compat = compat, kompat

        if isinstance(position, dict):
            # TODO: any mapping
            position = SourcePosition(**position)
        elif not isinstance(position, SourcePosition):
            # list, tuple, any iterable
            position = SourcePosition(*position)

        self.position, self.description = (
            position, description
        )

    def __top_half__(self, runtime):
        pass

    def __bottom_half__(self, runtime):
        pass

    def __happened__(self, *a, **kw):
        "Provides access to private `__notify_happened`"
        self.__notify_happened(*a, **kw)
