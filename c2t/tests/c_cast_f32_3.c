/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit int32_t
    volatile double a = 1370898521.0;
    volatile int32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
