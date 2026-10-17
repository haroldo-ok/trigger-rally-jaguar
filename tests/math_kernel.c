/* SPDX-License-Identifier: GPL-3.0-or-later
 * Separate 68000 arithmetic test cartridge. NOT used as game E2E evidence.
 * Host test only reads results; the real 68000 executes the arithmetic.
 */
#include <stdint.h>
typedef union { uint32_t u;float f; } Bits;
static uint32_t seed=0x54524a31u;
static uint32_t rng(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
void game_main(void){
    volatile uint32_t*t=(uint32_t*)0x1000,*out=(uint32_t*)0x4000;
    t[0]=0x4d415448;t[1]=0;t[2]=0;
    for(unsigned i=0;i<2048;i++){
        uint32_t x=rng(),y=rng();Bits a,b,m,d;
        a.u=(x&0x807fffffu)|((100u+(x>>24)%56)<<23);
        b.u=(y&0x807fffffu)|((100u+(y>>24)%56)<<23);
        m.f=a.f*b.f;d.f=a.f/b.f;
        out[i*4]=a.u;out[i*4+1]=b.u;out[i*4+2]=m.u;out[i*4+3]=d.u;t[1]=i+1;
    }
    t[2]=1;
}
