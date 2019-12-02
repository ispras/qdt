/* Control flow instruction */

#include <stdint.h>

int main(void)
{
    volatile int8_t a = 0xa, b = 0xb, c;
#if __MSP430__ == 1
    asm volatile goto (
        "jmp %l[label]"
        :
        : 
        :
        : label
    );
#else
    if (a) {
        goto label;
    }
#endif
    c = a;  //$br
label:
    c = b;  //$br

    return 0;   //$bre
}
