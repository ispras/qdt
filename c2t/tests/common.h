#ifndef C2T_TESTS_COMMON_H
#define C2T_TESTS_COMMON_H

#include <stdint.h>

/* There is a configuration of tests.
A `C2TConfig` may use `-D` option in `target_compiler` `args` to define
the settings. */

/* A CPU with a software pipeline may run several instructions simultaneously.
As a result several C statements run simultaneously too.
So, to check result of a statement it is not enough to set a breakpoint at
next statement, the pipeline must pass some stages before the breakpoint. */
#ifndef FLUSH_PIPELINE
#define FLUSH_PIPELINE
#endif /* FLUSH_PIPELINE */

#endif /* C2T_TESTS_COMMON_H */
