# SPDX-License-Identifier: GPL-3.0-or-later
# DSP startup and original three-voice PCM IRQ, in the bank opposite C code.
# C uses r25/r26 for its stacks; r31 is reserved for the interrupt stack.
.section .dspstart,"acrwx"
.space 16
serial_irq:
    load (r29),r28
    movei mix,r0
    jump (r0)
    nop
# Vector ends at +28; entry must start at +256.
.space 228
.global _dsp_entry
_dsp_entry:
    movei 0xf1a100,r29
    moveta r29,r29
    movei 0xf1cffc,r31
    moveta r31,r31
    movei 0x4000|0x3e00,r0
    store r0,(r29)
    nop
    nop
    movei 0xf1a150,r0
    movei 51,r1
    store r1,(r0)
    addq 4,r0
    moveq 13,r1
    store r1,(r0)
    movei 0x4000|0x3e00|0x20,r0
    store r0,(r29)
    nop
    nop
    movei 0xf1cfe0,r26
    movei 0x3fff0,r25
    movei dsp_halt,r27
    movei _game_main,r30
    jump (r30)
    nop
    nop
dsp_halt:
    jr dsp_halt
    nop
mix:
    moveq 0,r20
    moveq 3,r21
    movei 0x1800,r15
    movei phases,r14
channel:
    load (r15),r0
    btst 0,r0
    movei next,r27
    jump ne,(r27)
    nop
    load (r14),r1
    cmp r0,r1
    jr eq,same
    nop
    store r0,(r14)
    moveq 0,r2
    store r2,(r14+1)
same:
    load (r15+1),r3
    cmpq 0,r3
    movei next,r27
    jump eq,(r27)
    nop
    load (r14+1),r2
    move r2,r4
    shrq 8,r4
    load (r15+2),r5
    cmp r5,r4
    jr mi,in_sample
    load (r15+6),r6
    cmpq 0,r6
    movei next,r27
    jump eq,(r27)
    nop
    moveq 0,r2
    moveq 0,r4
in_sample:
    shlq 1,r4
    add r3,r4
    loadw (r4),r7
    shlq 16,r7
    sharq 16,r7
    load (r15+5),r8
    imult r8,r7
    sharq 8,r7
    add r7,r20
    load (r15+4),r8
    add r8,r2
    store r2,(r14+1)
next:
    addq 32,r15
    subq 1,r21
    movei channel,r27
    jump ne,(r27)
    addqt 8,r14
    movei 0xf1a148,r0
    store r20,(r0)
    addq 4,r0
    store r20,(r0)
    bset 10,r28
    bclr 3,r28
    load (r31),r30
    addq 2,r30
    addq 4,r31
    jump (r30)
    store r28,(r29)
.balign 8
phases:
.long 0,0,0,0,0,0
