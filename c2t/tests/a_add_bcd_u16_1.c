/* Arithmetic instruction */

#include <stdint.h>

#if __MSP430__ == 1
#include "msp430.h"
#else
// https://stackoverflow.com/questions/29875541/binary-coded-decimal-addition-using-integer
uint16_t median(uint16_t x, uint16_t y, uint16_t z)
{
    return (x & (y | z)) | (y & z);
}

uint16_t bcd_add_knuth(uint16_t x, uint16_t y)
{
    uint16_t z, u, t;
    z = y + 0x6666;
    u = x + z;
    t = median(~x, ~z, u) & 0x8888;
    return u - t + (t >> 2);
}
#endif

void main(void)
{
    volatile uint16_t a = 0x1234, b = 0x3456, c;

#if __MSP430__ == 1
    c = __bcd_add_short(a, b);
#else
    c = bcd_add_knuth(a, b);
#endif
    c = 0;     //$ch.c

    return;    //$bre
}
