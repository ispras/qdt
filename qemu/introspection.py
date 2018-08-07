__all__ = [
    "SourcePosition",
    "QEvent",
    "q_event_dict",
    "q_event_list"
]

from common import (
    notifier
)

# Events are valid for this QEMU version
# 4743c23509a51bd4ee85cc272287a41917d1be35
# v2.12.0

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
        """ This function is called when a QEMU debug information becomes
        available.

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
class QEvent(object):
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


q_event_list = [
    QEvent(
        ("type_register_internal",),
        "QOM Type registration"
    ),
    QEvent(
        ("object_initialize_with_type", 379,),
        "Object initialization started"
    ),
    QEvent(
        ("object_initialize_with_type", 386,),
        "Object initialization finished"
    ),
]

q_event_dict = {}

for e in q_event_list:
    q_event_dict[e.description] = e
