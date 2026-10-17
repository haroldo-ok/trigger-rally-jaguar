/* SPDX-License-Identifier: GPL-3.0-or-later
 * Real 68000 cartridge bootstrap for Virtual Jaguar's BIOS-disabled/HLE path.
 * The signed GPU SBL remains the BIOS/hardware boot path. Both end up running
 * the SAME linked native program at its header-specified RAM destination.
 * This code executes from cartridge ROM; it never relies on preloaded RAM.
 */
.section .text,"ax"
.global cart_boot
cart_boot:
    move.w #0x2700,%sr
    movea.l #0x10fff0,%sp
    move.l #0,0xf02114       /* stop a leftover GPU job on reset */
    move.l #0,0xf1a114       /* stop DSP before replacing its program */
    move.w #0,0xf000e0       /* disable 68000 video interrupts */
    movea.l #0x800410,%a0
    movea.l 0x800414,%a1     /* native program destination */
    movea.l %a1,%a2
    move.l 0x800418,%d0     /* native image length, excludes BSS */
    addq.l #3,%d0
    lsr.l #2,%d0
    subq.l #1,%d0
1:  move.l (%a0)+,(%a1)+
    subq.l #1,%d0
    bpl.s 1b
    jmp (%a2)
.section .note.GNU-stack,"",@progbits
