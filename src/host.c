/* SPDX-License-Identifier: GPL-3.0-or-later
 * Freestanding 68000 host: genuine dual-path cartridge startup is retained.
 * The complete game/simulation now executes on the real Jaguar DSP; the
 * requested 42Bastian engine remains on the GPU. No faster emulator clock.
 */
#include <stdint.h>
#ifndef TR_DSP_IMAGE_HEADER
#define TR_DSP_IMAGE_HEADER "dsp/image.h"
#endif
#include TR_DSP_IMAGE_HEADER
extern const unsigned char dsp_program[];
#define R32(a) (*(volatile uint32_t *)(a))
void game_main(void){
    uint32_t *p=(uint32_t*)0x14000;
    for(unsigned n=0;n<(0x40000-0x14000)/4;n++)p[n]=0;
    /* Read cartridge bytes directly: destination may overlap the RAM copy
       made by either boot loader, but never the ROM source or this host. */
    const uint32_t *src=(const uint32_t*)(0x800410u+(uint32_t)dsp_program-0x10000u);
    for(unsigned n=0;n<DSP_IMAGE_BYTES/4;n++)p[n]=src[n];
    p=(uint32_t*)0xf1b000;src=(const uint32_t*)DSP_LOCAL_LOAD;
    for(unsigned n=0;n<DSP_LOCAL_BYTES/4;n++)p[n]=src[n];
    R32(0xf1a100)=0x7e00;R32(0xf1a110)=0xf1b100;R32(0xf1a114)=1;
    for(;;)__asm__ volatile("stop #0x2700");
}
