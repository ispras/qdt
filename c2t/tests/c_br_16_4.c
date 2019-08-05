/* Control flow instruction */

#include <stdint.h>

void main(void)
{
    volatile int16_t a = 0xdef6, b = 0xd42f, c = 0;

    if (a < b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
