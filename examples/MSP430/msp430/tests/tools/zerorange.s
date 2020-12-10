; r4 - start, r5 - end
zerorange:
bic #1, r4 ; align

_zerorange_loop:
cmp r5, r4
jhs _zeromem_ret
mov.w #0, @r4
incd r4
jmp _zerorange_loop

_zeromem_ret:
ret
