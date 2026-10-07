/* Control flow instruction */

#include "common.h"

int main(void)
{
    volatile uint8_t a = 0x8, b = 0xaa, c;
#if __MSP430__ == 1
    asm volatile goto (
        "bit.b %[src_a], %[dst_b] \n\
         jc %l[label]"
        :
        : [dst_b] "rm" (b),
          [src_a] "rm" (a)
        : "cc"
        : label
    );
#else
    if (a & b) {
        goto label;
    }
#endif

    FLUSH_PIPELINE;

    c = a;  //$br

    FLUSH_PIPELINE;

label:

    FLUSH_PIPELINE;

    c = b;  //$br

    FLUSH_PIPELINE;

    return 0;   //$bre
}
