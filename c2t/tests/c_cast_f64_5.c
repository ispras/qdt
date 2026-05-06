/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile double a;
    volatile int64_t b = -98469723469582;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
