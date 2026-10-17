# SPDX-License-Identifier: GPL-3.0-or-later
# Native JRISC arithmetic ABI used by the C compiler. No runtime library link.
.section .dsp,"acrwx"
.balign 4
.global ___mulint32,___mulint32dsp
___mulint32:
___mulint32dsp:
    move r0,r2
    move r1,r3
    rorq 16,r2
    rorq 16,r3
    mult r1,r2
    mult r0,r3
    mult r1,r0
    add r3,r2
    shlq 16,r2
    jump (r27)
    add r2,r0
.balign 4
.global ___divint32,___divint32dsp
___divint32:
___divint32dsp:
    move r0,r2
    xor r1,r2
    abs r0
    abs r1
    div r1,r0
    sharq 31,r2
    xor r2,r0
    jump (r27)
    sub r2,r0
.balign 4
.global ___moduint32,___moduint32dsp
___moduint32:
___moduint32dsp:
    move r2,r0
    div r3,r0
    move r0,r4
    move r3,r5
    rorq 16,r4
    rorq 16,r5
    mult r3,r4
    mult r0,r5
    mult r3,r0
    add r5,r4
    shlq 16,r4
    add r4,r0
    sub r0,r2
    jump (r27)
    move r2,r0
.balign 4
.global ___modint32,___modint32dsp
___modint32:
___modint32dsp:
    move r0,r6
    sharq 31,r6
    abs r0
    abs r1
    move r0,r2
    move r1,r3
    move r27,r7
    move pc,r27
    addq 8,r27
    jr ___moduint32
    nop
    xor r6,r0
    jump (r7)
    sub r6,r0
