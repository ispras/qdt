/* Extended tests: integer abs */

#include "common.h"

#include <stdlib.h>

void main(void)
{
    volatile int32_t a = -123456789, b;

    b = abs(a);

    FLUSH_PIPELINE;

    b = 0;     //$ch.b

    FLUSH_PIPELINE;

    return;    //$bre
}
