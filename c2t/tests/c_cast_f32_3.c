/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a = 1370898521.487079;
    volatile int32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
