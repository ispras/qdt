/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a = 20363956191232.0;
    volatile uint32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
