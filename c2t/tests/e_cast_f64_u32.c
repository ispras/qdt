/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a;
    volatile uint32_t b = 0x87654321;

    a = b;

    FLUSH_PIPELINE;

    a = 0;     //$ch.a

    FLUSH_PIPELINE;

    return;    //$bre
}
