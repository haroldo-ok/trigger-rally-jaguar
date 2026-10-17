/* SPDX-License-Identifier: GPL-3.0-or-later */
.section .rodata.dsp_image,"a"
.balign 8
.global dsp_program,dsp_program_end
dsp_program:
#ifndef TR_DSP_IMAGE_FILE
#define TR_DSP_IMAGE_FILE "assets/dsp_game.bin"
#endif
.incbin TR_DSP_IMAGE_FILE
dsp_program_end:
.section .note.GNU-stack,"",@progbits
