#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Rebuild the signed homebrew loader from src/boot.js.

Ordinary builds use the included deterministic 0x410-byte boot.XXX. This
optional target needs 42Bastian/pc_jagcrypt, which supports -q -u -tursi.
No retail game ROM or external Jaguar BIOS is consumed by this build step.
"""
import argparse,os,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--assembler',type=Path,default=R/'vendor/lyxass/lyxass');p.add_argument('--sdk',type=Path,default=R/'vendor/new_bjl');p.add_argument('--jagcrypt',type=Path,default=Path(os.environ.get('JAGCRYPT',str(R.parent/'tools/jagcrypt/jagcrypt'))));a=p.parse_args()
if not a.jagcrypt.exists():raise SystemExit('Set JAGCRYPT=/path/to/42Bastian/pc_jagcrypt/jagcrypt. Pinned revision: a7d582b8097a6c185a6840e22059d3b82866b938. See docs/BUILDING.md.')
(R/'artifacts').mkdir(exist_ok=True)
e=dict(os.environ,BJL_ROOT=str(a.sdk.resolve()))
subprocess.run([str(a.assembler.resolve()),'-d','-o','artifacts/boot.bin','src/boot.js'],cwd=R,env=e,check=True)
subprocess.run([str(a.jagcrypt.resolve()),'-q','-u','-tursi','artifacts/boot.bin'],cwd=R,check=True)
b=(R/'artifacts/boot.XXX').read_bytes();assert len(b)<=0x410
(R/'src/boot.XXX').write_bytes(b.ljust(0x410,b'\0'))
print('Rebuilt signed native bootstrap: src/boot.XXX (1040 bytes)')
