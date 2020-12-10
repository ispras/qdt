.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push @r0

.word 0x1210 ;push 0(r0)
.word 0

push r0
subc 2(r1), 0(r1)
br_1:

.include "tools/pop_regs.s"

ret
