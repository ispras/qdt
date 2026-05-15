/* Cast instruction */

#include "common.h"

void main(void)
{
    // must fit uint64_t
    volatile double a = 1370898521487e4;
    volatile uint64_t b;

    b = a;
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
