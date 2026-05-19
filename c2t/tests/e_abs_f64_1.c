/* Extended tests: double precision float-point abs */

#include "common.h"

#include <math.h>

void main(void)
{
    volatile double a = -1.234567890123e10, b;

    b = fabs(a);
    FLUSH_PIPELINE;
    b = 0;     //$ch.b

    return;    //$bre
}
