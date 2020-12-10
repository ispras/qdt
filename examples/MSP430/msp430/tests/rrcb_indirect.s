.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push #0x1234
mov r1, r5
rrc.b @r5
br_1:

.include "tools/pop_regs.s"

ret
