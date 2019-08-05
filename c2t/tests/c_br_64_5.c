/* Control flow instruction */

#include <stdint.h>

void main(void)
{
    volatile int64_t a = 0x2cae02f54de81641, b = 0x29bb30a986b60314, c = 0;

    if (a >= b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
