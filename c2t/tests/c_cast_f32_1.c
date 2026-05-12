/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a = 2036395619.0;
    volatile int32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
