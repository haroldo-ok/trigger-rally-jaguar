#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent arithmetic/render unit cartridge executed by the real Jaguar DSP.

Never substitutes this unit cartridge for game E2E. The host supplies no target
RAM/CPU writes: Jerry produces all results; NumPy is only a read-only oracle.
"""
from pathlib import Path
import argparse,hashlib,json,math,struct,subprocess,sys
import numpy as np
from vj import VJ
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from build_dsp_game import build
p=argparse.ArgumentParser();p.add_argument('--core',type=Path,default=R/'vendor/bin/virtualjaguar_libretro.so');a=p.parse_args()
W=R/'.cache/dsp-math';W.mkdir(parents=True,exist_ok=True);image=W/'dsp.bin';header=W/'image.h'
def run(cmd):subprocess.run(list(map(str,cmd)),cwd=R,check=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=sha(R/'releases/trigger-rally-jaguar.j64')
build(R/'tests/dsp_math_kernel.c',output=image,work_dir=W/'dsp-build',header_path=header)
run(['m68k-linux-gnu-gcc','-m68000','-msoft-float','-O2','-ffreestanding','-fno-pie','-fno-stack-protector','-DTR_DSP_IMAGE_HEADER="'+str(header)+'"','-c','src/host.c','-o',W/'host.o'])
run(['m68k-linux-gnu-gcc','-m68000','-DTR_DSP_IMAGE_FILE="'+str(image)+'"','-c','src/dsp_blob.S','-o',W/'blob.o'])
run(['m68k-linux-gnu-gcc','-m68000','-nostdlib','-static','-no-pie','-Wl,--build-id=none,--gc-sections,-T,src/jaguar.ld','-Wl,-Map,'+str(W/'program.map'),'artifacts/start.o',W/'host.o',W/'blob.o','-o',W/'program.elf'])
run(['m68k-linux-gnu-objcopy','-O','binary',W/'program.elf',W/'program.bin'])
boot=(R/'src/boot.XXX').read_bytes();code=(W/'program.bin').read_bytes();rom=bytearray(b'\xff'*0x400000)
rom[:len(boot)]=boot;struct.pack_into('>I',rom,0x404,0x83f000);rom[0x410:0x410+len(code)]=code;h=(R/'artifacts/cartboot.bin').read_bytes();rom[0x3f000:0x3f000+len(h)]=h
path=W/'DSP-MATH-TEST-ONLY.j64';path.write_bytes(rom)
v=VJ(a.core,path,bios=False)
try:
    for i in range(600):
        v.step()
        if v.u32(0x1000)==0x4453504d and v.u32(0x1008)==1:break
    assert v.u32(0x1008)==1,'DSP test did not finish: '+str(v.debug())
    rows=np.frombuffer(v.read(0x120000,2048*32),dtype='>u4').astype(np.uint32).reshape(-1,8)
    x=rows[:,0].copy().view(np.float32);y=rows[:,1].copy().view(np.float32);n=rows[:,6].copy().view(np.int32)
    with np.errstate(all='ignore'):
        expectations=[(2,'add',x+y),(3,'subtract',x-y),(4,'multiply',x*y),(5,'divide',x/y),(7,'integer_conversion',n.astype(np.float32))]
    result={'pass':True,'test':'actual Jaguar DSP binary32, basic aggregate ABI and render-only fixed-point matrices','test_cartridge_sha256':sha(path),'core_sha256':sha(a.core),'cases':2048,'arithmetic_operations':10240,'emulator_frames':v.frame,'mismatches':{},'first_errors':{},'aggregate_result':v.u32(0x1100),'live_aggregate_field':hex(v.u32(0x1104)),'coverage':'Signed normal/subnormal/zero/infinite/NaN arithmetic and full-range int32 conversion. NaN payload bits are unspecified and checked only for NaN classification; not exhaustive IEEE exceptions or optimizer/ABI validation.'}
    for col,name,expected in expectations:
        bits=expected.astype(np.float32).view(np.uint32);nan=(bits&0x7fffffff)>0x7f800000;got=rows[:,col]
        bad=np.flatnonzero(((bits!=got)&~nan)|(nan&((got&0x7fffffff)<=0x7f800000)));result['mismatches'][name]=len(bad)
        if len(bad):
            result['pass']=False;i=int(bad[0]);result['first_errors'][name]={k:hex(int(z)) for k,z in zip(['a','b','n','got','expected'],[rows[i,0],rows[i,1],rows[i,6],got[i],bits[i]])}
    actual=np.frombuffer(v.read(0x1140,80),dtype='>u4').astype(np.uint32);expected=[];acc=np.float32(.1);step=np.float32(1/150)
    for _ in range(20):expected.append(acc.view(np.uint32));acc=np.float32(acc-step)
    result['decrement_sequence_mismatches']=int(np.count_nonzero(actual!=expected));result['pass'] &= result['decrement_sequence_mismatches']==0
    render=np.frombuffer(v.read(0x140000,64*24*4),dtype='>i4').astype(np.int64).reshape(64,24);sine=np.array([round(math.sin(i*2*math.pi/512)*32767) for i in range(512)],dtype=np.int64)
    exact_bad=0;max_matrix_error=0.
    for j,row in enumerate(render):
        basis=row[:9].reshape(3,3);actual_wheel=row[9:18].reshape(3,3);local=row[18:21];position=row[21:24]
        sy=sine[(j*7)&511];cy=sine[(j*7+128)&511];sx=sine[(j*19)&511];cx=sine[(j*19+128)&511];want=np.empty((3,3),dtype=np.int64)
        for r in range(3):
            aa,yy,cc=map(int,basis[r]);xx=(aa*cy-cc*sy+16384)>>15;hh=(aa*sy+cc*cy+16384)>>15;y1=(hh*sx+yy*cx+16384)>>15;zz=(hh*cx-yy*sx+16384)>>15;want[r]=[-xx if j&1 else xx,-y1 if j&1 else y1,zz]
        exact_bad+=int(np.count_nonzero(want!=actual_wheel));exact_bad+=int(np.count_nonzero(((basis@local+16384)>>15)!=position))
        steer=(j*7&511)*2*math.pi/512;spin=(j*19&511)*2*math.pi/512
        ry=np.array([[math.cos(steer),0,math.sin(steer)],[0,1,0],[-math.sin(steer),0,math.cos(steer)]])
        rx=np.array([[1,0,0],[0,math.cos(spin),-math.sin(spin)],[0,math.sin(spin),math.cos(spin)]]);flip=np.diag([-1,-1,1] if j&1 else [1,1,1])
        oracle=basis.astype(float)/32768@ry@rx@flip;max_matrix_error=max(max_matrix_error,float(np.max(np.abs(oracle-actual_wheel/32768))))
    result['render_matrix_cases']=64;result['render_integer_mismatches']=exact_bad;result['maximum_render_matrix_error_vs_rotation_oracle']=max_matrix_error
    result['pass'] &= exact_bad==0 and max_matrix_error<8/32768 and result['aggregate_result']==6 and result['live_aggregate_field']=='0x12345678'
    inputs=['tests/dsp_math_kernel.c','tests/check_dsp_math.py','src/dsp/float32.c','src/dsp/float_fast.s','src/dsp/integers.s','src/dsp/start.s','src/render_math.c','src/render_tables.h','tools/build_dsp_game.py','tools/patches/vbcc-jrisc-binary32.patch']
    result['sources_sha256']={f:sha(R/f) for f in inputs};result['released_game_unchanged']=sha(R/'releases/trigger-rally-jaguar.j64')==original;result['pass'] &= result['released_game_unchanged']
    (R/'artifacts/dsp-math-report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['pass']
finally:v.close()
