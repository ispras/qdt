/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit uint32_t
    volatile float a = 234e7;
    volatile uint32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
