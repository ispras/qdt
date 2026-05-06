/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a = 20363956191232.0;
    volatile uint64_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
