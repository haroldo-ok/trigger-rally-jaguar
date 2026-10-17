# SPDX-License-Identifier: GPL-3.0-or-later
# Binary32 hot paths. C ABI: a=r2, b=r3, result=r0, LR=r27.
# Only volatile registers are touched. Unusual exponents use the complete C
# implementation, with original arguments intact. All operations run on Jerry.
.section .dsp,"acrwx"
.balign 4
.global ___tr_mul,___tr_mul_slow
___tr_mul:
    movei ___tr_mul_slow,r30
    movei 0x7fffffff,r1
    move r2,r7
    move r3,r8
    and r1,r7
    and r1,r8
    movei 0x7f800000,r1
    cmp r1,r7
    jump hs,(r30)
    nop
    cmp r1,r8
    jump hs,(r30)
    nop
    move r2,r4
    xor r3,r4
    movei 0x80000000,r1
    and r1,r4
    cmpq 0,r7
    jr eq,mul_zero
    nop
    cmpq 0,r8
    jr eq,mul_zero
    nop
    move r7,r5
    move r8,r6
    shrq 23,r5
    shrq 23,r6
    cmpq 0,r5
    jump eq,(r30)
    nop
    cmpq 0,r6
    jump eq,(r30)
    nop
    add r6,r5
    movei 127,r1
    sub r1,r5
    movei 0x7fffff,r1
    and r1,r7
    and r1,r8
    movei 0x800000,r1
    or r1,r7
    or r1,r8
    movei 4095,r1
    move r7,r9
    move r8,r11
    and r1,r9
    and r1,r11
    move r7,r10
    move r8,r12
    shrq 12,r10
    shrq 12,r12
    move r9,r14
    move r9,r13
    mult r11,r14
    mult r12,r13
    move r10,r9
    mult r11,r9
    add r9,r13
    move r14,r9
    shrq 12,r9
    add r9,r13
    move r10,r0
    mult r12,r0
    shlq 4,r0
    move r13,r9
    shrq 8,r9
    add r9,r0
    and r1,r14
    movei 255,r1
    and r1,r13
    or r14,r13
    jr eq,mul_no_sticky
    nop
    bset 0,r0
mul_no_sticky:
    btst 27,r0
    jr eq,fp_round
    nop
    move r0,r1
    shrq 1,r0
    btst 0,r1
    jr eq,mul_shift_done
    nop
    bset 0,r0
mul_shift_done:
    jr fp_round
    addq 1,r5
mul_zero:
    jump (r27)
    move r4,r0

.balign 4
.global ___tr_sub,___tr_add,___tr_add_slow
___tr_sub:
    movei 0x80000000,r0
    xor r0,r3
___tr_add:
    movei ___tr_add_slow,r30
    movei 0x7fffffff,r1
    move r2,r6
    move r3,r7
    move r2,r4
    move r3,r5
    and r1,r4
    and r1,r5
    movei 0x7f800000,r1
    cmp r1,r4
    jump hs,(r30)
    nop
    cmp r1,r5
    jump hs,(r30)
    nop
    cmpq 0,r4
    jr eq,add_a_zero
    nop
    cmpq 0,r5
    jr eq,add_b_zero
    nop
    cmp r5,r4
    jr hs,add_ordered
    nop
    move r4,r0
    move r5,r4
    move r0,r5
    move r6,r0
    move r7,r6
    move r0,r7
add_ordered:
    move r4,r8
    shrq 23,r8
    move r5,r9
    shrq 23,r9
    cmpq 0,r8
    jump eq,(r30)
    nop
    cmpq 0,r9
    jump eq,(r30)
    nop
    movei 0x7fffff,r1
    and r1,r4
    and r1,r5
    movei 0x800000,r1
    or r1,r4
    or r1,r5
    shlq 3,r4
    shlq 3,r5
    move r8,r10
    sub r9,r10
    cmpq 0,r10
    jr eq,add_aligned
    nop
    movei 32,r1
    cmp r1,r10
    jr lo,add_shift
    nop
    jr add_aligned
    moveq 1,r5
add_shift:
    move r5,r11
    move r1,r12
    sub r10,r12
    neg r12
    sh r12,r11
    sh r10,r5
    cmpq 0,r11
    jr eq,add_aligned
    nop
    bset 0,r5
add_aligned:
    move r2,r11
    xor r3,r11
    move r4,r0
    btst 31,r11
    jr ne,add_subtract
    nop
    add r5,r0
    move r8,r5
    movei 0x80000000,r1
    move r6,r4
    and r1,r4
    btst 27,r0
    jr eq,fp_round
    nop
    move r0,r1
    shrq 1,r0
    btst 0,r1
    jr eq,add_carry_done
    nop
    bset 0,r0
add_carry_done:
    jr fp_round
    addq 1,r5
add_subtract:
    sub r5,r0
    jr eq,add_cancel
    nop
    move r8,r5
    movei 0x80000000,r1
    move r6,r4
    and r1,r4
add_normalize:
    btst 26,r0
    jr ne,fp_round
    nop
    shlq 1,r0
    jr add_normalize
    subq 1,r5
add_cancel:
    jump (r27)
    moveq 0,r0
add_a_zero:
    cmpq 0,r5
    jr eq,add_both_zero
    nop
    jump (r27)
    move r3,r0
add_both_zero:
    move r2,r0
    jump (r27)
    and r3,r0
add_b_zero:
    jump (r27)
    move r2,r0

# Shared normalized-significand rounder: sig=r0 (24+3 bits), exp=r5,
# sign=r4. r30 remains the appropriate slow-path address.
.balign 4
fp_round:
    cmpq 0,r5
    jump mi,(r30)
    nop
    jump eq,(r30)
    nop
    movei 255,r1
    cmp r1,r5
    jump hs,(r30)
    nop
    move r0,r1
    moveq 7,r6
    and r6,r1
    shrq 3,r0
    cmpq 4,r1
    jr hi,fp_round_up
    nop
    jr ne,fp_pack
    nop
    btst 0,r0
    jr eq,fp_pack
    nop
fp_round_up:
    addq 1,r0
    btst 24,r0
    jr eq,fp_pack
    nop
    shrq 1,r0
    addq 1,r5
fp_pack:
    movei 255,r1
    cmp r1,r5
    jump hs,(r30)
    nop
    movei 0x7fffff,r1
    and r1,r0
    shlq 23,r5
    or r5,r0
    jump (r27)
    or r4,r0

.balign 4
.global ___tr_div,___tr_div_slow
___tr_div:
    movei ___tr_div_slow,r30
    movei 0x7fffffff,r1
    move r2,r7
    move r3,r8
    and r1,r7
    and r1,r8
    movei 0x7f800000,r1
    cmp r1,r7
    jump hs,(r30)
    nop
    cmp r1,r8
    jump hs,(r30)
    nop
    cmpq 0,r8
    jump eq,(r30)
    nop
    move r2,r4
    xor r3,r4
    movei 0x80000000,r1
    and r1,r4
    cmpq 0,r7
    jr eq,div_zero
    nop
    move r7,r5
    move r8,r6
    shrq 23,r5
    shrq 23,r6
    cmpq 0,r5
    jump eq,(r30)
    nop
    cmpq 0,r6
    jump eq,(r30)
    nop
    sub r6,r5
    movei 127,r1
    add r1,r5
    movei 0x7fffff,r1
    and r1,r7
    and r1,r8
    movei 0x800000,r1
    or r1,r7
    or r1,r8
    cmp r8,r7
    jr hs,div_normalized
    nop
    shlq 1,r7
    subq 1,r5
div_normalized:
    # Reconstruct exact remainders. Do not rely on Jerry's REMAIN latch.
    move r7,r9
    shlq 7,r9
    move r9,r10
    div r8,r9
    move r8,r13
    move r8,r14
    mult r9,r13
    shrq 16,r14
    mult r9,r14
    shlq 16,r14
    add r14,r13
    sub r13,r10
    move r9,r11
    shlq 16,r11
    move r10,r9
    shlq 8,r9
    move r9,r10
    div r8,r9
    move r8,r13
    move r8,r14
    mult r9,r13
    shrq 16,r14
    mult r9,r14
    shlq 16,r14
    add r14,r13
    sub r13,r10
    shlq 8,r9
    or r9,r11
    move r10,r9
    shlq 8,r9
    move r9,r10
    div r8,r9
    move r8,r13
    move r8,r14
    mult r9,r13
    shrq 16,r14
    mult r9,r14
    shlq 16,r14
    add r14,r13
    sub r13,r10
    or r9,r11
    move r11,r0
    shlq 3,r0
    shlq 1,r10
    cmp r8,r10
    jr lo,div_tail_low
    nop
    bset 2,r0
div_tail_low:
    cmpq 0,r10
    jr eq,fp_round
    nop
    cmp r8,r10
    jr eq,fp_round
    nop
    jr fp_round
    bset 0,r0
div_zero:
    jump (r27)
    move r4,r0

.balign 4
.global ___tr_cmp
___tr_cmp:
    move r2,r4
    move r3,r5
    shlq 1,r4
    shlq 1,r5
    or r5,r4
    jr eq,cmp_equal
    nop
    cmp r3,r2
    jr eq,cmp_equal
    nop
    move r2,r4
    xor r3,r4
    btst 31,r4
    jr eq,cmp_same_sign
    moveq 1,r0
    btst 31,r2
    jr eq,cmp_done
    nop
    jump (r27)
    neg r0
cmp_same_sign:
    cmp r3,r2
    jr hs,cmp_ordered
    nop
    neg r0
cmp_ordered:
    btst 31,r2
    jr eq,cmp_done
    nop
    neg r0
cmp_done:
    jump (r27)
    nop
cmp_equal:
    jump (r27)
    moveq 0,r0
