/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int16_t a = 0x8012, b = 0x8078, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}
