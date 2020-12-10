.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

setc
subc.b r0, r4
br_1:
push #4
setc
subc.b r0, 0(r1)
br_2:
pop r4

.include "tools/pop_regs.s"

ret
