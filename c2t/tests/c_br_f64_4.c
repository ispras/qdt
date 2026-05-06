/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile double a = 375315.48926803726, b = 2.927828385643325e-212, c = 0;

    if (a < b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
