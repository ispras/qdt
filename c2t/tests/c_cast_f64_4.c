/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a = 1370898521487.079;
    volatile uint32_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
