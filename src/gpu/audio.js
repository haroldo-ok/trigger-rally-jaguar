; SPDX-License-Identifier: GPL-3.0-or-later
; Three-voice signed PCM mixer. Engine and skid loop; SFX is one-shot.
; 8.8 sample phases support all converted samples, including the long voice clip.
    dsp
    include <js/symbols/jagregeq.js>
    run $f1b000
    org $f1b010
serial_irq:
    load (r29),r28
    movei #mix,r0
    jump (r0)
    nop
    org $f1b100
init_audio::
    movei #DSP_FLAGS,r29
    moveta r29,r29
    movei #$f1bffc,r31
    moveta r31,r31
    movei #$4000|$3e00,r0
    store r0,(r29)
    nop
    nop
    movei #SCLK,r0
    movei #51,r1
    store r1,(r0)
    addq #4,r0
    moveq #13,r1
    store r1,(r0)
    movei #$4000|$3e00|$20,r0
    store r0,(r29)
idle:
    jr idle
    nop
mix:
    moveq #0,r20
    moveq #3,r21
    movei #$1800,r15
    movei #phases,r14
channel:
    load (r15),r0
    btst #0,r0
    movei #next,r27
    jump ne,(r27)
    nop
    load (r14),r1
    cmp r0,r1
    jr eq,same
    nop
    store r0,(r14)
    moveq #0,r2
    store r2,(r14+4)
same:
    load (r15+4),r3
    cmpq #0,r3
    movei #next,r27
    jump eq,(r27)
    nop
    load (r14+4),r2
    move r2,r4
    shrq #8,r4
    load (r15+8),r5
    cmp r5,r4
    jr mi,in_sample
    load (r15+24),r6
    cmpq #0,r6
    movei #next,r27
    jump eq,(r27)
    nop
    moveq #0,r2
    moveq #0,r4
in_sample:
    shlq #1,r4
    add r3,r4
    loadw (r4),r7
    shlq #16,r7
    sharq #16,r7
    load (r15+20),r8
    imult r8,r7
    sharq #8,r7
    add r7,r20
    load (r15+16),r8
    add r8,r2
    store r2,(r14+4)
next:
    addq #32,r15
    subq #1,r21
    movei #channel,r27
    jump ne,(r27)
    addqt #8,r14
    movei #L_I2S,r0
    store r20,(r0)
    addq #4,r0
    store r20,(r0)
    bset #10,r28
    bclr #3,r28
    load (r31),r30
    addq #2,r30
    addq #4,r31
    jump (r30)
    store r28,(r29)
    align 8
phases:
    dc.l 0,0,0,0,0,0
    align 8
end_audio::
    end
