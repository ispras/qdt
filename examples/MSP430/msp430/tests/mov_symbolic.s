.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

mov 0, r5
br_1:

.include "tools/pop_regs.s"

ret
