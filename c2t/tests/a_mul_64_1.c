/* Arithmetic instruction */

#include "common.h"

void main(void)
{
    volatile int64_t a = 0xa897f6ec7ba90619, b = 0x17ab32c02, c;

    c = a * b;
    c = 0;     //$ch.c

    return;    //$bre
}
