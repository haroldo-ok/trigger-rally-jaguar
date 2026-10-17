/* SPDX-License-Identifier: GPL-3.0-or-later
 * DSP game image is copied from cartridge to main RAM by the 68000 loader.
 * Hot binary32/integer routines and audio IRQ execute from real DSP local RAM.
 */
MEMORY {
  ram: org=0x14000, len=0x2a000
  dsp: org=0xf1b000, len=0x1d00
}
SECTIONS {
  .text: { *(.text CODE text .rodata rodata) RESERVE(ALIGN(32)-.); } >ram
  .data: { *(.data DATA data) RESERVE(ALIGN(32)-.); } >ram
  _dsp_local_load = ADDR(.data)+SIZEOF(.data);
  .local: { *(.dspstart) *(.dsp .dsp_*) RESERVE(ALIGN(32)-.); } >dsp AT>ram
  _dsp_local_bytes = SIZEOF(.local);
  .bss (NOLOAD): { *(.bss BSS bss COMMON) .=ALIGN(32); } >ram
  _dsp_bss_start = ADDR(.bss);
  _dsp_bss_end = ADDR(.bss)+SIZEOF(.bss);
}
