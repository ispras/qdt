/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile double
        a = 375315.48926803726,
        b = 2.927828385643325e-212,
        c = 0;

    if (a >= b) {
        FLUSH_PIPELINE;

        c = 1;  //$br

        FLUSH_PIPELINE;
    } else {
        FLUSH_PIPELINE;

        c = -1; //$br

        FLUSH_PIPELINE;
    }

    FLUSH_PIPELINE;

    return;     //$bre
}
