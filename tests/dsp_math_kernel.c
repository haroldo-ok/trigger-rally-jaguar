/* SPDX-License-Identifier: GPL-3.0-or-later
 * Separate actual-DSP binary32/render test; NEVER a distributed game ROM.
 */
#include <stdint.h>
#include "render_math.h"
typedef union { uint32_t u;float f; } Bits;
static uint32_t seed=0x54524a31u;
static uint32_t rng(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
typedef struct { uint32_t a,b,c,keep; } Record;
static volatile uint32_t *result=(uint32_t*)0x1100;
static __noinline uint32_t consume(Record r){return r.a+r.b+r.c;}
static const uint32_t edge[]={0,0x80000000u,1,0x80000001u,0x7fffffu,0x807fffffu,0x800000u,0x80800000u,0x3f800000u,0xbf800000u,0x7f7fffffu,0xff7fffffu,0x7f800000u,0xff800000u,0x7fc00000u,0x3dcccccd};
void game_main(void){
    volatile uint32_t*t=(uint32_t*)0x1000,*out=(uint32_t*)0x120000;
    t[0]=0x4453504d;t[1]=0;t[2]=0;
    Record r={1,2,3,0x12345678};result[0]=consume(r);result[1]=r.keep;
    for(unsigned i=0;i<2048;i++){
        uint32_t x=rng(),y=rng();Bits a,b,sum,sub,m,d,conv;
        a.u=i<64?edge[i%16]:(i<1024?(x&0x807fffffu)|((100u+(x>>24)%56)<<23):x);
        b.u=i<64?edge[(i*7+i/16)%16]:(i<1024?(y&0x807fffffu)|((100u+(y>>24)%56)<<23):y);
        sum.f=a.f+b.f;sub.f=a.f-b.f;m.f=a.f*b.f;d.f=a.f/b.f;
        int32_t n=(int32_t)x;conv.f=(float)n;
        out[i*8]=a.u;out[i*8+1]=b.u;out[i*8+2]=sum.u;out[i*8+3]=sub.u;
        out[i*8+4]=m.u;out[i*8+5]=d.u;out[i*8+6]=(uint32_t)n;out[i*8+7]=conv.u;t[1]=i+1;
    }
    float acc=.1f;
    for(unsigned j=0;j<20;j++){Bits z;z.f=acc;result[16+j]=z.u;acc-=1.f/150;}
    result[40]=(uint32_t)(acc<0);
    volatile int32_t*render=(int32_t*)0x140000;
    for(unsigned j=0;j<64;j++){
        int32_t basis[9],wheel[9],pos[3];int16_t local[3]={(int)j*7-200,120-(int)j*3,(int)j*11-300};
        render_z_matrix(j*13,basis);
        if(j&1)for(unsigned k=0;k<3;k++){int32_t temp=basis[k+3];basis[k+3]=basis[k+6];basis[k+6]=temp;}
        render_wheel_matrix(basis,j*7,j*19,j&1,wheel);render_transform(basis,local,pos);
        for(unsigned k=0;k<9;k++){render[j*24+k]=basis[k];render[j*24+9+k]=wheel[k];}
        for(unsigned k=0;k<3;k++){render[j*24+18+k]=local[k];render[j*24+21+k]=pos[k];}
    }
    t[2]=1;
}
