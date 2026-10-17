#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Reproducibly encode the native Jaguar OP lists used by the adapted engine.

Equivalent to src/gpu/obl.S for this port's fixed 384x200 CRY16 / 384x40
1-bit HUD layout. List design: 42Bastian/jag_3d_engine (MIT). Object phrases
follow Jaguar hardware layout; no prebuilt-list patching or ROM patching.
PAL's HUD needs its own safe vertical start: the old 30-line placement lost
the title/counter above desktop Virtual Jaguar's visible PAL region.
"""
from pathlib import Path
import re,struct
R=Path(__file__).resolve().parents[1]
video=(R/'src/gpu/video.h').read_text()
sdk=(R/'vendor/new_bjl/js/symbols/jagregeq.js').read_text()
def integer(text,key):
    m=re.search(r'^'+re.escape(key)+r'\s+equ\s+(\d+(?:\s*\*\s*\d+)?)',text,re.I|re.M)
    if not m:raise ValueError('Missing literal OP-layout constant: '+key)
    value=1
    for factor in m[1].split('*'):value*=int(factor)
    return value
x=integer(video,'max_x');y=integer(video,'max_y');tx=max(x,320);ty=integer(video,'max_y_txt')
assert (x,y,tx,ty)==(384,200,384,40),'Update the OP encoder when changing native video geometry'
text=0x1ffff0-(tx//8)*ty
framebytes=((x*y*2+31)&~31)*2
screen1=(text&0xfffff00)-framebytes;logo=screen1-80

def bitmap(data,link,vertical,height):
    assert data%8==0 and link%8==0 and 0<=vertical<2048 and height<1024
    return ((data>>3)<<43)|((link>>3)<<24)|(height<<14)|(vertical<<3)
def branch(link,condition,vertical):return ((link>>3)<<24)|(condition<<14)|(vertical<<3)|3
def attributes(xpos,depth,pitch,dwidth,iwidth,index=0,transparent=False):
    return xpos|(depth<<12)|(pitch<<15)|(dwidth<<18)|(iwidth<<28)|(index<<38)|(int(transparent)<<47)|(1<<48)

for standard,hz in [('pal',50),('ntsc',60)]:
    start=integer(video,'y_start_'+standard)*2
    hud=integer(video,'y_text_'+standard)*2
    vde=2*((integer(sdk,standard+'_VMID')+integer(sdk,standard+'_HEIGHT'))//2+1)
    for i in [0,1]:
        words=[branch(0x420,1,start),branch(0x440,1,vde),branch(0x420,2,vde),0x12,4,0,0,0,
               bitmap(screen1+(8 if i==0 else 0),0x450,start,y),attributes(20,4,2,x//2,x//4),
               bitmap(text,0x460,hud,ty),attributes(20,0,1,tx//64,tx//64,127),
               bitmap(logo,0x470,start+380,9),attributes(20,0,1,1,1,transparent=True),4,0]
        p=R/f'src/gpu/obl{i}_{hz}.bin';p.write_bytes(struct.pack('>16Q',*words))
        print(p.relative_to(R),len(words)*8,'bytes; HUD Y =',hud,'half-lines')
