/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile float a = -2.5383766896286625e-16, b = 2.3519078240497038e-08, c;

    c = a * b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}

