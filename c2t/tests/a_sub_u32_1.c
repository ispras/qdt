/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile uint32_t a = 0x1df473e4, b = 0x58bac230, c;

    c = a - b;

    FLUSH_PIPELINE;

    c = 0;     //$ch.c

    FLUSH_PIPELINE;

    return;    //$bre
}
