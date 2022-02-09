.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

mov.b #-2, r4
mov.b #1, r5
setc
addc.b r4, r5
br_1:

.include "tools/pop_regs.s"

ret
