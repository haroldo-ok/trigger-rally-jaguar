/* SPDX-License-Identifier: GPL-3.0-or-later */
.section .boot,"ax"
.global _start
_start:
    bra.w start2
    .long _start
    .long __image_end-_start
    .long 0
start2:
    move.w #0x2700,%sr
    movea.l #0x10fff0,%sp
    lea __bss_start,%a0
    lea __bss_end,%a1
1:  cmpa.l %a1,%a0
    bcc.s 2f
    clr.l (%a0)+
    bra.s 1b
2:  jsr game_main
3:  stop #0x2700
    bra.s 3b
/* A genuine compatibility entry for frontends hard-wired to $802000.
 * The signed loader and universal-header $83f000 entry remain unchanged. */
.section .compat.boot,"ax"
.global compat_cart_entry
compat_cart_entry:
    jmp 0x83f000
.section .rodata,"a"
.balign 8
.global gpu_blob,gpu_blob_end,audio_blob,audio_blob_end,font_blob
gpu_blob:
.incbin "assets/gpu.bin"
gpu_blob_end:
.balign 8
audio_blob:
.incbin "assets/audio.bin"
audio_blob_end:
.balign 8
font_blob:
.incbin "src/font8x8.bin"
.section .note.GNU-stack,"",@progbits
