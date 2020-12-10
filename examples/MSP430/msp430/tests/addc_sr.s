.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

mov #-2, r4
setc
addc r2, r4
br_1:

.include "tools/pop_regs.s"

ret
