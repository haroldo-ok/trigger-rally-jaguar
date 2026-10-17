/* SPDX-License-Identifier: GPL-3.0-or-later
 * Binary32 arithmetic for the Jaguar DSP, using its integer ALU/multiplier.
 * Values keep the original asset/runtime IEEE-754 representation. The source
 * simulation is compiled without changing its equations or integration rate.
 * Round-to-nearest, ties-to-even; gradual underflow and signed infinities.
 * No host arithmetic, altered emulator clock, or memory-patched physics.
 */
#include <stdint.h>
#ifdef __VBCC__
#define LOCAL __dsplocal
static uint32_t umul16(__reg("r1") uint32_t a,__reg("r2") uint32_t b) =
    "\tmove r1,r0\n\tmult r2,r0\n";
#else
#define LOCAL
static inline uint32_t umul16(uint32_t a,uint32_t b){return a*b;}
#endif
#define SIGN 0x80000000u
#define INF 0x7f800000u
#define NAN32 0x7fc00000u
static inline uint32_t jam(uint32_t a,unsigned n){
    if(!n)return a;
    if(n>=32)return a!=0;
    return (a>>n)|((a<<(32-n))!=0);
}
static inline unsigned clz32(uint32_t n){
    unsigned c=0;if(!n)return 32;
    if(!(n&0xffff0000u)){n<<=16;c+=16;}
    if(!(n&0xff000000u)){n<<=8;c+=8;}
    if(!(n&0xf0000000u)){n<<=4;c+=4;}
    if(!(n&0xc0000000u)){n<<=2;c+=2;}
    if(!(n&0x80000000u))c++;
    return c;
}
static inline uint32_t pack(uint32_t sign,int exp,uint32_t sig){
    if(exp<=0){sig=jam(sig,1-exp);exp=1;}
    uint32_t frac=sig>>3,tail=sig&7;
    if(tail>4||(tail==4&&(frac&1)))frac++;
    if(frac>=0x1000000u){frac>>=1;exp++;}
    if(exp>=255)return sign|INF;
    if(frac<0x800000u)exp=0;
    return sign|((uint32_t)exp<<23)|(frac&0x7fffffu);
}
LOCAL uint32_t __tr_add_slow(uint32_t a,uint32_t b){
    uint32_t aa=a&~SIGN,bb=b&~SIGN;
    if(aa>=INF||bb>=INF){
        if(aa>INF||bb>INF)return NAN32;
        if(aa==INF&&bb==INF&&((a^b)&SIGN))return NAN32;
        return aa==INF?a:b;
    }
    if(aa<bb){uint32_t t=a;a=b;b=t;t=aa;aa=bb;bb=t;}
    if(!bb)return aa?a:(a&b&SIGN);
    int ea=aa>>23,eb=bb>>23;
    uint32_t ma=aa&0x7fffffu,mb=bb&0x7fffffu;
    if(ea)ma|=0x800000u;else ea=1;
    if(eb)mb|=0x800000u;else eb=1;
    ma<<=3;mb=jam(mb<<3,ea-eb);
    uint32_t sign=a&SIGN;
    if((a^b)&SIGN){
        ma-=mb;if(!ma)return 0;
        unsigned shift=clz32(ma)-5;
        if((int)shift>ea-1)shift=ea-1;
        ma<<=shift;ea-=shift;
    }else{
        ma+=mb;if(ma&0x08000000u){ma=jam(ma,1);ea++;}
    }
    return pack(sign,ea,ma);
}
LOCAL uint32_t __tr_sub_slow(uint32_t a,uint32_t b){return __tr_add_slow(a,b^SIGN);}
LOCAL uint32_t __tr_neg(uint32_t a){return a^SIGN;}
LOCAL int __tr_tst(uint32_t a){return (a&~SIGN)!=0;}
LOCAL int __tr_cmp_slow(uint32_t a,uint32_t b){
    if(!(a&~SIGN)&&!(b&~SIGN))return 0;
    if(a==b)return 0;
    if((a^b)&SIGN)return a&SIGN?-1:1;
    int r=(a<b)?-1:1;return a&SIGN?-r:r;
}
LOCAL uint32_t __tr_mul_slow(uint32_t a,uint32_t b){
    uint32_t sign=(a^b)&SIGN,aa=a&~SIGN,bb=b&~SIGN;
    if(aa>=INF||bb>=INF){
        if(aa>INF||bb>INF||!aa||!bb)return NAN32;return sign|INF;
    }
    if(!aa||!bb)return sign;
    int ea=aa>>23,eb=bb>>23;
    uint32_t ma=(aa&0x7fffffu),mb=(bb&0x7fffffu);
    if(ea)ma|=0x800000u;else{unsigned n=clz32(ma)-8;ma<<=n;ea=1-(int)n;}
    if(eb)mb|=0x800000u;else{unsigned n=clz32(mb)-8;mb<<=n;eb=1-(int)n;}
    uint32_t al=ma&4095,ah=ma>>12,bl=mb&4095,bh=mb>>12;
    uint32_t lo=umul16(al,bl),mid=umul16(al,bh)+umul16(ah,bl)+(lo>>12);
    uint32_t sig=(umul16(ah,bh)<<4)+(mid>>8);
    sig|=((mid&255)|(lo&4095))!=0;
    int exp=ea+eb-127;
    if(sig&0x08000000u){sig=jam(sig,1);exp++;}
    return pack(sign,exp,sig);
}
LOCAL uint32_t __tr_div_slow(uint32_t a,uint32_t b){
    uint32_t sign=(a^b)&SIGN,aa=a&~SIGN,bb=b&~SIGN;
    if(aa>=INF||bb>=INF){
        if(aa>INF||bb>INF||(aa==INF&&bb==INF))return NAN32;
        return aa==INF?(sign|INF):sign;
    }
    if(!bb)return aa?(sign|INF):NAN32;if(!aa)return sign;
    int ea=aa>>23,eb=bb>>23;
    uint32_t ma=aa&0x7fffffu,mb=bb&0x7fffffu;
    if(ea)ma|=0x800000u;else{unsigned n=clz32(ma)-8;ma<<=n;ea=1-(int)n;}
    if(eb)mb|=0x800000u;else{unsigned n=clz32(mb)-8;mb<<=n;eb=1-(int)n;}
    int exp=ea-eb+127;if(ma<mb){ma<<=1;exp--;}
    uint32_t n=ma<<7,q=n/mb,r=n-q*mb;
    n=r<<8;uint32_t q2=n/mb;r=n-q2*mb;
    n=r<<8;uint32_t q3=n/mb;r=n-q3*mb;
    uint32_t frac=(q<<16)|(q2<<8)|q3;
    uint32_t tail=r*2>=mb?4:0;if(r&&r*2!=mb)tail|=1;
    return pack(sign,exp,(frac<<3)|tail);
}
LOCAL uint32_t __tr_fromu(uint32_t a){
    if(!a)return 0;unsigned n=clz32(a);int exp=158-(int)n;
    uint32_t sig=n>=5?a<<(n-5):jam(a,5-n);
    return pack(0,exp,sig);
}
LOCAL uint32_t __tr_fromi(int32_t a){
    uint32_t r=__tr_fromu(a<0?0u-(uint32_t)a:(uint32_t)a);return a<0?r|SIGN:r;
}
LOCAL uint32_t __tr_tou(uint32_t a){
    int e=(int)((a>>23)&255)-127;if(a&SIGN||e<0)return 0;
    if(e>31)return 0xffffffffu;uint32_t m=(a&0x7fffffu)|0x800000u;
    return e>=23?m<<(e-23):m>>(23-e);
}
LOCAL int32_t __tr_toi(uint32_t a){
    uint32_t n=__tr_tou(a&~SIGN);
    if(n>0x7fffffffu)return a&SIGN?(int32_t)SIGN:0x7fffffff;
    return a&SIGN?-(int32_t)n:(int32_t)n;
}
