__all__ = [
    "q_event_dict",
    "q_event_list"
]

from gdb import (
    Breakpoint
)

# Events are valid for this QEMU version
# 4743c23509a51bd4ee85cc272287a41917d1be35
# v2.12.0

q_event_list = [
    Breakpoint(
        ("type_register_internal",),
        "QOM Type registration"
    ),
    Breakpoint(
        ("object_initialize_with_type", 379,),
        "Object initialization started"
    ),
    Breakpoint(
        ("object_initialize_with_type", 386,),
        "Object initialization finished"
    ),
]

q_event_dict = {}

for e in q_event_list:
    q_event_dict[e.description] = e
