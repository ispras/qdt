/* Control flow instruction */

#include <stdint.h>

void main(void)
{
    volatile int8_t a = 0x2f, b = 0xed, c = 0;

    if (a >= b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
