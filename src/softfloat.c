/* SPDX-License-Identifier: GPL-3.0-or-later
 * IEEE-754 binary32 / integer conversions for the Jaguar's plain 68000.
 * The Linux m68k libgcc conversion objects require a 68881, so they MUST NOT
 * be linked into this cartridge. Arithmetic is GCC's genuine 68000 software
 * implementation (vendor/lb1sf68.S), compiled locally with -m68000.
 */
#include <stdint.h>
typedef union {float f;uint32_t u;} Bits;
float __floatunsisf(uint32_t n){
    Bits r;if(!n){r.u=0;return r.f;}
    unsigned e=0;uint32_t t=n;while(t>>1){t>>=1;e++;}
    uint32_t m;
    if(e<=23)m=n<<(23-e);
    else {unsigned shift=e-23;uint32_t rem=n&((1u<<shift)-1),half=1u<<(shift-1);m=n>>shift;
        if(rem>half||(rem==half&&(m&1)))m++;
        if(m==0x1000000){m>>=1;e++;}}
    r.u=((e+127)<<23)|(m&0x7fffff);return r.f;
}
float __floatsisf(int32_t n){Bits r;r.f=__floatunsisf(n<0?0u-(uint32_t)n:(uint32_t)n);if(n<0)r.u|=0x80000000;return r.f;}
uint32_t __fixunssfsi(float f){
    Bits b;b.f=f;int e=(int)((b.u>>23)&255)-127;
    if(b.u>>31||e<0)return 0;if(e>31)return 0xffffffffu;
    uint32_t m=(b.u&0x7fffff)|0x800000;return e>=23?m<<(e-23):m>>(23-e);
}
int32_t __fixsfsi(float f){
    Bits b;b.f=f;int neg=b.u>>31;b.u&=0x7fffffff;uint32_t n=__fixunssfsi(b.f);
    if(n>0x7fffffffu)return neg?(int32_t)0x80000000:0x7fffffff;
    return neg?-(int32_t)n:(int32_t)n;
}
