/* Control flow instruction */

#include <stdint.h>

int main(void)
{
    volatile uint16_t a = 0x8, b = 0xaa, c;
#if __MSP430__ == 1
    asm volatile goto (
        "bit.w %[src_a], %[dst_b] \n\
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
    c = a;  //$br
label:
    c = b;  //$br

    return 0;   //$bre
}
