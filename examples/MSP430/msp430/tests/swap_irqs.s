.global test

test:

.include "tools/push_regs.s"
.include "tools/enum_regs.s"

push r2
bic #8, r2
nop
bis #8, r2
pop r2
br_1:

.include "tools/pop_regs.s"

ret
