/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit uint32_t
    volatile double a = 3370898521.079;
    volatile uint32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
