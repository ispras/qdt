/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a;
    // must fit mantissa
    volatile int64_t b = -0x46e1df00000000;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
