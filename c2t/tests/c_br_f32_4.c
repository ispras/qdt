/* Control flow instruction */

#include "common.h"

void main(void)
{
    volatile float a = 1.292059605610279e-29, b = -6.066191494664202e-32, c = 0;

    if (a < b) {
        c = 1;  //$br
    } else {
        c = -1; //$br
    }

    return;     //$bre
}
