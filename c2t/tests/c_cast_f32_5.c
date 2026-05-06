/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a;
    volatile int32_t b = -56757234;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
