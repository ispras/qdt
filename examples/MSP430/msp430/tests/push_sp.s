.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

mov #0x240, r4
mov #0x260, r5
call #zerorange

mov r1, r5
decd r5 ; don't zero ret addr
mov r1, r4
sub #20, r4
call #zerorange

sub #10, r1

push r1
br_1:
pop r1
push.w #0x250
pop r1
br_2:
mov r5, r1

.include "tools/pop_regs.s"

ret

.include "tools/zerorange.s"
