/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit int64_t
    volatile float a = 20363956191232.0;
    volatile int64_t b;

    b = a;

    FLUSH_PIPELINE;

    b = 0;     //$ch.b

    FLUSH_PIPELINE;

    return;    //$bre
}
