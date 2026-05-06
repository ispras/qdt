/* Cast instruction */

#include "common.h"

void main(void)
{
    volatile float a;
    volatile int64_t b = -57865912873491823;

    a = b;
    FLUSH_PIPELINE;
    a = 0;     //$ch.a

    return;    //$bre
}
