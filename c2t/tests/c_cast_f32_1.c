/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit int32_t
    volatile float a = 1e9;
    volatile int32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
