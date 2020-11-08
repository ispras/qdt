/* Control flow instruction */

#include <stdint.h>

volatile int16_t a[6] = {1, 2, 3, 4, 5, 0};

void main(void)
{
    volatile int16_t *pa = a;
    volatile int16_t c;

#if __MSP430__ == 1
    asm volatile (
        "loop_start: cmp #0, @%[src] \n\
        jz loop_end \n\
        rra @%[src]+ \n\
        jmp loop_start \n\
        loop_end:"
        :
        : [src] "r" (pa)
        : "cc", "memory"
    );
#else
loop_start:
    if (*pa == 0) {
        goto loop_end;
    }
    *(pa++) = *pa / 2;
    goto loop_start;
loop_end:
#endif
    c = a[3];
    c = 0; //$ch.c

    return;    //$bre
}

