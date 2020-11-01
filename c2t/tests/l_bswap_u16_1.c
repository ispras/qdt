/* Logical instruction */

#include <stdint.h>

#if __MSP430__ == 1
#include "msp430.h"
#endif

void main(void)
{
    volatile uint16_t a = 0x1234, c;

#if __MSP430__ == 1
    c = __swap_bytes(a);
#else
    c = ((a >> 8) & 0xFF) | ((a & 0xFF) << 8);
#endif
    c = 0;     //$ch.c

    return;    //$bre
}
