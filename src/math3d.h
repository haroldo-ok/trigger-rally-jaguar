/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef TR_MATH3D_H
#define TR_MATH3D_H
#include "data.h"
#define PI 3.14159265358979323846f
#define TAU (2*PI)
static inline float minf(float a,float b){return a<b?a:b;}
static inline float maxf(float a,float b){return a>b?a:b;}
static inline float absf(float a){return a<0?-a:a;}
static inline float clampf(float a,float l,float h){return minf(h,maxf(l,a));}
static inline float lerpf(float a,float b,float t){return a+(b-a)*t;}
static inline float pull(float a,float b,float t){return lerpf(a,b,minf(1,t));}
static inline float toward(float a,float b,float d){return a<b?minf(a+d,b):maxf(a-d,b);}
/* Two Newton refinements: relative error < 5e-6 for normal positive
 * binary32 inputs. Avoids four software divisions per vector normalization. */
static inline float rsqrtf_local(float a){
    if(a<=0)return 0;
    union {float f;uint32_t i;} u={a};u.i=0x5f375a86u-(u.i>>1);
    float x=u.f,h=.5f*a;
    x=x*(1.5f-h*x*x);return x*(1.5f-h*x*x);
}
static inline float sqrtf_local(float a){return a>0?a*rsqrtf_local(a):0;}
static inline float sinf_local(float x){
    while(x>PI)x-=TAU;while(x< -PI)x+=TAU;
    if(x>PI/2)x=PI-x;if(x< -PI/2)x=-PI-x;
    float s=x*x;return x*(1+s*(-1.f/6+s*(1.f/120+s*(-1.f/5040+s/362880))));
}
static inline float cosf_local(float x){return sinf_local(x+PI/2);}
static inline float atan2f_local(float y,float x){
    if(x==0)return y>0?PI/2:y<0?-PI/2:0;
    float a=absf(y),b=absf(x),z=minf(a,b)/maxf(a,b),s=z*z;
    float r=z*(.999866f+s*(-.3302995f+s*(.180141f+s*(-.085133f+s*.0208351f))));
    if(a>b)r=PI/2-r;if(x<0)r=PI-r;return y<0?-r:r;
}
static inline float asinf_local(float x){return atan2f_local(clampf(x,-1,1),sqrtf_local(maxf(0,1-x*x)));}
static inline float acosf_local(float x){return PI/2-asinf_local(x);}
static inline float logf_local(float x){
    int e=0;while(x>1.5f){x*=.5f;e++;}while(x<.75f){x*=2;e--;}
    float z=(x-1)/(x+1),s=z*z;return 2*z*(1+s*(1.f/3+s*(1.f/5+s/7)))+e*.69314718f;
}
static inline V3 v3(float x,float y,float z){V3 a={x,y,z};return a;}
static inline V3 add(V3 a,V3 b){return v3(a.x+b.x,a.y+b.y,a.z+b.z);}
static inline V3 sub(V3 a,V3 b){return v3(a.x-b.x,a.y-b.y,a.z-b.z);}
static inline V3 mul(V3 a,float s){return v3(a.x*s,a.y*s,a.z*s);}
static inline float dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
static inline V3 cross(V3 a,V3 b){return v3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);}
static inline float length(V3 a){return sqrtf_local(dot(a,a));}
static inline V3 normalized(V3 a){float s=dot(a,a);return s>1e-16f?mul(a,rsqrtf_local(s)):v3(0,0,1);}
static inline Q4 qm(Q4 a,Q4 b){Q4 q={a.x*b.w+a.w*b.x+a.y*b.z-a.z*b.y,a.y*b.w+a.w*b.y+a.z*b.x-a.x*b.z,a.z*b.w+a.w*b.z+a.x*b.y-a.y*b.x,a.w*b.w-a.x*b.x-a.y*b.y-a.z*b.z};return q;}
static inline Q4 qnorm(Q4 a){float s=rsqrtf_local(a.x*a.x+a.y*a.y+a.z*a.z+a.w*a.w);Q4 q={a.x*s,a.y*s,a.z*s,a.w*s};return q;}
static inline Q4 qaxis(V3 a,float angle){float s=sinf_local(angle/2);Q4 q={a.x*s,a.y*s,a.z*s,cosf_local(angle/2)};return q;}
static inline void qmatrix(Q4 q,float *m){
    m[0]=1-2*(q.y*q.y+q.z*q.z);m[1]=2*(q.x*q.y-q.z*q.w);m[2]=2*(q.x*q.z+q.y*q.w);
    m[3]=2*(q.x*q.y+q.z*q.w);m[4]=1-2*(q.x*q.x+q.z*q.z);m[5]=2*(q.y*q.z-q.x*q.w);
    m[6]=2*(q.x*q.z-q.y*q.w);m[7]=2*(q.y*q.z+q.x*q.w);m[8]=1-2*(q.x*q.x+q.y*q.y);
}
static inline V3 mv(const float*m,V3 a){return v3(dot(v3(m[0],m[1],m[2]),a),dot(v3(m[3],m[4],m[5]),a),dot(v3(m[6],m[7],m[8]),a));}
static inline V3 mtv(const float*m,V3 a){return v3(dot(v3(m[0],m[3],m[6]),a),dot(v3(m[1],m[4],m[7]),a),dot(v3(m[2],m[5],m[8]),a));}
#endif
