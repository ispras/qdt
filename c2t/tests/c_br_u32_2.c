/* Control flow instruction */

#include <stdint.h>

void main(void)
{
    volatile uint32_t a = 0x192ce100, b = 0x4b4da436, c = 0;

    if (a != b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
