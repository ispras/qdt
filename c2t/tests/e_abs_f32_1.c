/* Extended tests: float-point abs */

#include "common.h"

#include <math.h>

void main(void)
{
    volatile float a = -1.2345e23, b;

    b = fabsf(a);
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
