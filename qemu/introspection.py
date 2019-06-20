__all__ = [
]

# Events are valid for this QEMU version
# 4743c23509a51bd4ee85cc272287a41917d1be35
# v2.12.0

class SourcePosition(object):
    def __init__(self,
        file_path = None,
        line_number = None,
        function_name = None,
        **compat # forward compatibility
    ):
        self.compat = compat

        if function_name is None:
            if file_path is None or line_number is None:
                raise ValueError("To few data to identify a position.")
            """TODO: Given file:line look the corresponding function up or
            raise the ValueError."""
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

        self.file_path, self.line_number, self.function_name = (
            file_path, line_number, function_name
        )

class Event(object):
    def __init__(self,
        position,
    ):
        """
        :position:
            Instance of `SourcePosition`
        """
