#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the pinned JRISC toolchain from UNMODIFIED vendored source archives.

The project patch is applied only to the private build cache. Upstream vbcc
allows unmodified-archive redistribution/noncommercial use; see its license.
No vbcc C runtime or other proprietary library is linked into the game.
"""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tarfile
R=Path(__file__).resolve().parents[1]
W=R/'.cache/jrisc';B=W/'bin';V=R/'vendor/jrisc'
def run(cmd,cwd,**kwargs):
    print('+',' '.join(map(str,cmd)),flush=True)
    subprocess.run(list(map(str,cmd)),cwd=cwd,check=True,**kwargs)
def main():
    W.mkdir(parents=True,exist_ok=True);B.mkdir(exist_ok=True)
    sources=json.loads((V/'sources.json').read_text())
    for name,record in sources.items():
        p=V/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256'],name
        if not (W/name.split('.')[0]).exists():
            with tarfile.open(p) as t:t.extractall(W,filter='data')
    c=W/'vbcc';patch=R/'tools/patches/vbcc-jrisc-binary32.patch'
    stamp=c/'.trigger-binary32-patch'
    fingerprint=hashlib.sha256(patch.read_bytes()).hexdigest()
    if not stamp.exists():
        run(['patch','-p1','-i',patch],c);stamp.write_text(fingerprint)
    else:assert stamp.read_text()==fingerprint,'Remove .cache/jrisc to rebuild a revised compiler patch'
    # dtgen is interactive. Feed defaults explicitly, once, before parallel make.
    (c/'objects/jrisc').mkdir(parents=True,exist_ok=True)
    run(['make','TARGET=jrisc','bin/dtgen'],c)
    if not (c/'objects/jrisc/dt.h').exists():
        run(['bin/dtgen','machines/jrisc/machine.dt','objects/jrisc/dt.h','objects/jrisc/dt.c'],c,input=b'\n'*200)
    run(['make','TARGET=jrisc','-j4','bin/vbccjrisc','bin/vscjrisc'],c)
    (W/'vasm/obj').mkdir(exist_ok=True)
    (W/'vlink/objects').mkdir(exist_ok=True)
    run(['make','CPU=jagrisc','SYNTAX=std','-j4'],W/'vasm')
    run(['make','-j4'],W/'vlink')
    for src in [c/'bin/vbccjrisc',c/'bin/vscjrisc',W/'vasm/vasmjagrisc_std',W/'vlink/vlink']:
        dst=B/src.name;shutil.copy2(src,dst);dst.chmod(0o755)
    (W/'build.json').write_text(json.dumps({'sources':sources,'patch_sha256':fingerprint,'binaries':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in B.iterdir()}},indent=2)+'\n')
    print('JRISC source-built tools ready:',B,flush=True)
if __name__=='__main__':main()
