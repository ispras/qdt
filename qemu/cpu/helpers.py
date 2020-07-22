__all__ = [
    "underscored_name_shortener"
]

from collections import (
    defaultdict,
)
from itertools import (
    count,
)

def underscored_name_shortener(arguments, text):
    existing_names = defaultdict(lambda : count(0))
    for a in arguments:
        parts = a.name.split('_')
        if len(parts) > 1:
            # Argument names with underscores are shortened.
            # Only the first and second part of the name are used.
            # The first letter is taken from the first part.
            # If the first part of the name ends with a number, then it
            # is also taken.
            i = len(parts[0]) - 1
            while parts[0][i].isdigit():
                i = i - 1
            name = parts[0][0] + parts[0][i + 1:] + parts[1]
        else:
            name = a.name
        # Getting a unique name among all arguments by adding a sequence
        # number.
        while True:
            num = next(existing_names[name])
            if num > 0:
                print('Warning: auto-counter on the arg "%s" of the'
                    ' "%s" instruction' % (a.name, text)
                )
                name = name + str(num)
            else:
                break
        a.name = name
