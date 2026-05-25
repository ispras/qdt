/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a;
    // must fit mantissa
    volatile uint32_t b = 0x3feef3;

    a = b;

    FLUSH_PIPELINE;

    a = 0;     //$ch.a

    FLUSH_PIPELINE;

    return;    //$bre
}
