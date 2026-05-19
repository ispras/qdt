/* Extended tests: long integer abs */

#include "common.h"

#include <stdlib.h>

void main(void)
{
    volatile int64_t a = -123456789012345, b;

    b = llabs(a);
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
