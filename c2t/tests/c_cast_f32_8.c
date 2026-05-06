/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a;
    volatile uint64_t b = 0x8abbccddee0011ff;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
