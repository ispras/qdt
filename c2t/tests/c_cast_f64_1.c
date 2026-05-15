/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit int64_t
    volatile double a = 137089852e7;
    volatile int64_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
