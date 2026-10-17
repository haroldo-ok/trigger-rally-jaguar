/* SPDX-License-Identifier: GPL-3.0-or-later
 * Render-only native fixed-point matrix composition. This is the same
 * Body * RY(steer) * RX(spin) * RZ(flip) order as the source quaternion path.
 * No suspension, contact, gearbox, engine, flight or recovery force is removed.
 */
#include "render_math.h"
#include "render_tables.h"
#ifdef __JRISC__
static int32_t im16(__reg("r1") int32_t a,__reg("r2") int32_t b)=
    "\tmove r1,r0\n\timult r2,r0\n";
#else
static inline int32_t im16(int32_t a,int32_t b){return a*b;}
#endif
void render_transform(const int32_t*m,const int16_t*p,int32_t*out){
    for(unsigned i=0;i<3;i++)out[i]=(im16(m[i*3],p[0])+im16(m[i*3+1],p[1])+im16(m[i*3+2],p[2])+16384)>>15;
}
void render_wheel_matrix(const int32_t*b,unsigned steer,unsigned spin,int flip,int32_t*m){
    int32_t sy=render_sine[steer&511],cy=render_sine[(steer+128)&511];
    int32_t sx=render_sine[spin&511],cx=render_sine[(spin+128)&511];
    for(unsigned r=0;r<3;r++){
        int32_t a=b[r*3],c=b[r*3+2],y=b[r*3+1];
        int32_t x=(im16(a,cy)-im16(c,sy)+16384)>>15;
        int32_t h=(im16(a,sy)+im16(c,cy)+16384)>>15;
        int32_t yy=(im16(h,sx)+im16(y,cx)+16384)>>15;
        int32_t z=(im16(h,cx)-im16(y,sx)+16384)>>15;
        m[r*3]=flip?-x:x;m[r*3+1]=flip?-yy:yy;m[r*3+2]=z;
    }
}
void render_z_matrix(unsigned phase,int32_t*m){
    int32_t s=render_sine[phase&511],c=render_sine[(phase+128)&511];
    m[0]=c;m[1]=-s;m[2]=0;m[3]=s;m[4]=c;m[5]=0;m[6]=0;m[7]=0;m[8]=32767;
}

