.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push 2(r0)
br_1:

.include "tools/pop_regs.s"

ret
