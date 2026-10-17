#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Execute 4096 real 68000 float operations inside Virtual Jaguar.

This is a UNIT TEST cartridge, deliberately separate from the actual game ROM.
The native-game end-to-end test is e2e_virtual_jaguar.py.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,struct,time
import numpy as np
from vj import VJ
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--core',type=Path,default=R/'vendor/bin/virtualjaguar_libretro.so');a=p.parse_args()
subprocess.run(['make','artifacts/math.bin'],cwd=R,check=True)
boot=(R/'src/boot.XXX').read_bytes();code=(R/'artifacts/math.bin').read_bytes()
rom=bytearray(b'\xff'*0x100000);rom[:len(boot)]=boot;rom[0x410:0x410+len(code)]=code
path=R/'artifacts/math-test.j64';path.write_bytes(rom)
v=VJ(a.core,path)
try:
    for _ in range(1200):
        v.step()
        if v.u32(0x1000)==0x4d415448 and v.u32(0x1008)==1:break
    assert v.u32(0x1008)==1,'Math cartridge did not finish: '+str(v.debug())
    rows=np.frombuffer(v.read(0x4000,2048*16),dtype='>u4').astype(np.uint32).reshape(-1,4)
    x=rows[:,0].copy().view(np.float32);y=rows[:,1].copy().view(np.float32)
    m=(x*y).view(np.uint32);d=(x/y).view(np.uint32)
    # Correctly rounded binary32 results, checked bit for bit, not a loose tolerance.
    bad_m=np.where(m!=rows[:,2])[0];bad_d=np.where(d!=rows[:,3])[0]
    result={'test':'68000 softfloat / real Virtual Jaguar','cases':len(rows),'operations':4096,'emulator_frames':v.frame,'multiply_mismatches':len(bad_m),'divide_mismatches':len(bad_d),'pass':not len(bad_m) and not len(bad_d),'test_cartridge_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'core_sha256':hashlib.sha256(a.core.read_bytes()).hexdigest(),'coverage':'Deterministic signed normal binary32 inputs, exponents 100..155. Not exhaustive IEEE-754, integer-conversion, rsqrt or game-physics parity validation.'}
    for label,bad,col,expected in [('multiply',bad_m,2,m),('divide',bad_d,3,d)]:
        if len(bad):result[label+'_first_error']={k:hex(int(z)) for k,z in zip(['a','b','got','expected'],[rows[bad[0],0],rows[bad[0],1],rows[bad[0],col],expected[bad[0]]])}
    (R/'artifacts/math-report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert result['pass']
finally:v.close()
