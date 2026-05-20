/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile double a = -4.562228484338099e+252, b = 1.370898521487079e+56, c;

    c = a - b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
