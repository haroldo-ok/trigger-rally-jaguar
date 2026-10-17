# SPDX-License-Identifier: GPL-3.0-or-later
.section .rodata,"a"
.balign 8
.global _gpu_blob,_gpu_blob_end,_font_blob
_gpu_blob:
.incbin "assets/gpu.bin"
_gpu_blob_end:
.balign 8
_font_blob:
.incbin "src/font8x8.bin"
