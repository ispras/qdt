/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a;
    volatile uint32_t b = 0x8feef00d;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
