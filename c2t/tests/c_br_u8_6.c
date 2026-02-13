/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile uint8_t a = 0x5d, b = 0xf9, c = 0;

    if (a <= b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
