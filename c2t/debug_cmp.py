__all__ = [
    "DebugComparison"
]


class DebugComparison(object):
    """ This class compares values of debugging variables and displays
comparison report
"""

    def __init__(self, o_cmp_queue, t_cmp_queue):
        self.o_cmp_queue = o_cmp_queue
        self.t_cmp_queue = t_cmp_queue

    @staticmethod
    def __print_report(msg, hdump, tdump):
        dumps = {
            'HOST': hdump,
            'TARGET': tdump
        }

        print(msg)

        for dump in dumps:
            lineno = dumps[dump].values()[0]['lineno']
            address = dumps[dump].keys().pop()
            variables = dumps[dump].values()[0]['variables']
            regs = dumps[dump].values()[0]['regs'].split(' ')

            print('%s dump:\n'
                '    Source code line number: %d\n'
                '    Instruction address: %s\n'
                '    Variables: %s\n'
                '    Registers: %s' %
                (dump, lineno, address, variables,
                    ''.join(['\n               %s ' % reg
                        if i and not (i % 3) else '%s ' % reg
                        for i, reg in enumerate(regs)
                    ]) +
                    '\n'
                )
            )

    def start(self):
        """ Start debug comparison """
        while True:
            oracle_dump = self.o_cmp_queue.get(block=True)
            target_dump = self.t_cmp_queue.get(block=True)
            if oracle_dump == 'CMP_EXIT' and target_dump == 'CMP_EXIT':
                break
            else:
                if (oracle_dump == 'CMP_EXIT'
                    or target_dump == 'CMP_EXIT'
                    or oracle_dump.values()[0]['lineno'] !=
                        target_dump.values()[0]['lineno']):
                    self.__print_report('\n#ERROR: Debug comparison error '
                        '-- branch instruction error!\n\n', oracle_dump,
                        target_dump
                    )
                elif (oracle_dump.values()[0]['variables'] !=
                        target_dump.values()[0]['variables']):
                    self.__print_report('\n#ERROR: Debug comparison error '
                        '-- binary instruction error!\n\n', oracle_dump,
                        target_dump
                    )
                else:
                    continue

                raise Exception

        print('\nOK\n')
