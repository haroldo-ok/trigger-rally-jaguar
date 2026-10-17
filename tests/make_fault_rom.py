#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile real faulty cartridges; never patch a running emulator's memory.

Entry faults stop the real 68000 before it can launch the DSP game. Post-boot
faults are instrumented copies of the actual DSP C game; after eight completed
GPU frames they clear framebuffer/HUD RAM or freeze with the image retained.
All fault builds stay in the private cache; the released game is unchanged.
"""
from pathlib import Path
import argparse,hashlib,json,re,shlex,subprocess,sys,struct
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from build_dsp_game import build
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=['entry','black-after-boot','freeze-after-boot','no-acceleration','slow-racing'],required=True);p.add_argument('--rom',type=Path,default=R/'releases/trigger-rally-jaguar.j64');p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output=a.output.resolve();a.output.parent.mkdir(parents=True,exist_ok=True)
base=a.rom.read_bytes();rom=bytearray(base)
def run(cmd):subprocess.run(list(map(str,cmd)),cwd=R,check=True)
if a.kind=='entry':rom[0x410:0x412]=bytes.fromhex('60fe')
elif a.kind=='no-acceleration':
    # A real cartridge-data fault: controller input/renderer/game code stay
    # identical, but both engines have zero power. No running-RAM injection.
    cars=struct.unpack_from('>I',rom,0x40000+36)[0]
    count=struct.unpack_from('>I',rom,0x40000+12)[0]
    for i in range(count):
        offset=0x40000+cars-0x840000+i*612+552
        struct.pack_into('>f',rom,offset,0.)
else:
    run(['make','artifacts/program.bin'])
    flags=lambda key:shlex.split(re.search(r'^'+key+r' := (.+)$',(R/'Makefile').read_text(),re.M)[1])
    work=R/'.cache'/('negative-'+a.kind);work.mkdir(parents=True,exist_ok=True)
    source=(R/'src/main.c').read_text();needle='        TR_FENCE();T->command=1;';assert source.count(needle)==1
    if a.kind=='slow-racing':
        source=source.replace(needle,'        if(state==RACING)for(volatile unsigned stall=0;stall<200000;stall++){TR_IDLE();}\n'+needle)
    else:
        injection='        if(T->gpu_frames>=8&&T->vbl>=480){'
        if a.kind=='black-after-boot':injection+='memset((void*)0x1b4800,0,0x200000-0x1b4800);REG16(0xf00058)=0;'
        injection+='for(;;){TR_IDLE();}}\n'
        source=source.replace(needle,injection+needle)
    source=source.replace('#include "../assets/asset_ids.h"','#include "asset_ids.h"')
    c=work/'main.c';c.write_text(source);dsp=work/'dsp.bin';header=work/'image.h'
    build(output=dsp,main_source=c,work_dir=work/'dsp-build',header_path=header)
    cc='m68k-linux-gnu-gcc';host=work/'host.o';blob=work/'blob.o';elf=work/'program.elf';binary=work/'program.bin'
    run([cc,*flags('CFLAGS'),'-DTR_DSP_IMAGE_HEADER="'+str(header)+'"','-c','src/host.c','-o',host])
    run([cc,'-m68000','-DTR_DSP_IMAGE_FILE="'+str(dsp)+'"','-c','src/dsp_blob.S','-o',blob])
    run([cc,*flags('LDFLAGS'),'-Wl,-Map,'+str(work/'program.map'),'artifacts/start.o',host,blob,'-o',elf])
    run(['m68k-linux-gnu-objcopy','-O','binary',elf,binary]);code=binary.read_bytes();assert 0x410+len(code)<0x3f000
    rom[0x410:0x3f000]=b'\xff'*(0x3f000-0x410);rom[0x410:0x410+len(code)]=code
assert a.rom.read_bytes()==base,'The released cartridge was changed by a negative-control build'
a.output.write_bytes(rom)
print(json.dumps({'negative_control':a.kind,'base_rom_sha256':hashlib.sha256(base).hexdigest(),'fault_rom_sha256':hashlib.sha256(rom).hexdigest(),'output':str(a.output),'released_cartridge_unchanged':True,'native_fault_backend':'68000 entry' if a.kind=='entry' else 'cartridge engine power data' if a.kind=='no-acceleration' else 'actual DSP game source'},indent=2))
