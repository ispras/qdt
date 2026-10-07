/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit uint64_t
    volatile float a = 2036e15;
    volatile uint64_t b;

    b = a;

    FLUSH_PIPELINE;

    b = 0;     //$ch.b

    FLUSH_PIPELINE;

    return;    //$bre
}
