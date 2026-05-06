/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a;
    volatile uint64_t b = 0x87654321abcdef09;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
