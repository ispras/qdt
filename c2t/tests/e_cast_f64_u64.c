/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a;
    // must fit mantissa
    volatile uint64_t b = 0x87654321abcde000;

    a = b;

    FLUSH_PIPELINE;

    a = 0;     //$ch.a

    FLUSH_PIPELINE;

    return;    //$bre
}
