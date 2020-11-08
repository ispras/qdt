/* Logical instruction */

#include <stdint.h>

int main(void)
{
    volatile int16_t a = 0xedcb, b = 0x1234, c;

#if __MSP430__ == 1
    asm volatile (
        "mov %[src_b], %[dst_c] \n\
         bic %[src_a], %[dst_c]"
        : [dst_c] "=rm" (c)
        : [src_a] "rm" (a),
          [src_b] "rm" (b)
    );
#else
    c = ~a & b;
#endif
    c = 0;  //$ch.c

    return 0;   //$bre
}
