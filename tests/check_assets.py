#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check cartridge boundaries, target ABIs and REAL converted asset records.

This is structural validation, not a claim of complete feature/content parity.
"""
from pathlib import Path
import hashlib,json,struct,math
R=Path(__file__).resolve().parents[1];B=0x840000
b=(R/'assets/assets.bin').read_bytes();manifest=json.loads((R/'assets/manifest.json').read_text())
def block(p,n):
    assert B<=p<=B+len(b) and 0<=n<=B+len(b)-p,(hex(p),n,'outside asset bank')
    return b[p-B:p-B+n]
def ints(p,n):return struct.unpack('>'+str(n)+'I',block(p,n*4))
def floats(p,n):
    a=struct.unpack('>'+str(n)+'f',block(p,n*4));assert all(math.isfinite(x) for x in a);return a
h=struct.unpack('>13I',b[:52]);magic,version,nt,nc,nm,ntx,ns,size,tp,cp,mp,txp,sp=h
assert (magic,version,nt,nc)==(0x54524a31,1,3,2)
assert size==len(b)==manifest['assets_bytes']
assert ntx*8192<=0xe0000-0xb0000,'Texture upload overlaps scene descriptor RAM'
block(txp,ntx*8192)
checks=[]
for i in range(nm):
    p=mp+i*80;name=block(p,32).split(b'\0')[0].decode();r=ints(p+32,12)
    for nv,nf,pp,fp,np,vp in [(r[0],r[1],r[2],r[3],r[4],r[5]),(r[10],r[11],r[6],r[7],r[8],r[9])]:
        assert ints(pp,1)[0]==nv and ints(fp,1)[0]==nf
        assert ints(np,1)[0]==nf and ints(vp,1)[0]==nv
        block(pp,4+nv*8);block(fp,4+nf*12);block(np,4+nf*8);block(vp,4+nv*8)
        for j in range(nf):
            a,c,d,col,uv=struct.unpack('>4HI',block(fp+4+j*12,12))
            assert max(a,c,d)<nv
            if uv:
                index,*rest=struct.unpack('>8H',block(uv,16));assert index<ntx
    checks.append({'mesh':name,'full_triangles':r[11],'native_lod_triangles':r[1]})
assert any(c['mesh']=='checkpoint' and c['full_triangles']==384 for c in checks)
for i in range(nt):
    p=tp+i*108;floats(p+48,6);ncp,nsc,hp,colp,np,vp,surf,cpp,scp=ints(p+72,9)
    assert 0<ncp<=64 and nsc<=512
    for ptr,n in [(hp,128*128*2),(colp,128*128*2),(np,128*128*16),(vp,128*128*8),(surf,128*128),(cpp,ncp*36),(scp,nsc*36)]:block(ptr,n)
    for j in range(ncp):floats(cpp+j*36,9)
    for j in range(nsc):
        floats(scp+j*36,7);mesh,layer=ints(scp+j*36+28,2);assert mesh<nm and 1<=layer<=4
for i in range(nc):
    p=cp+i*612;wings,nw,nclips,npower,ngear=ints(p+68,5)
    assert nw<=4 and nclips<=16 and npower<=8 and ngear<=8
    floats(p+32,9);body,wheel=ints(p+604,2);assert body<nm and wheel<nm
for i in range(ns):
    p=sp+i*44;pcm,length,rate=ints(p+32,3);assert length>0 and rate==8000;block(pcm,length*2)
rom=(R/'releases/trigger-rally-jaguar.j64').read_bytes();info=json.loads((R/'releases/build-info.json').read_text())
assert len(rom)==4*1024*1024
assert rom[0x40000:0x40000+len(b)]==b
assert struct.unpack_from('>I',rom,0x404)[0]==0x83f000,'BIOS-disabled entry vector is wrong'
assert rom[0x3f000:0x3f000+info['hle_bootstrap_bytes']]==(R/'artifacts/cartboot.bin').read_bytes()
assert rom[:0x400]==(R/'src/boot.XXX').read_bytes()[:0x400], 'Signed GPU loader was changed'
assert 0x410+info['program_bytes']<0x3f000
assert struct.unpack_from('>I',rom,0x414)[0]==0x10000
assert struct.unpack_from('>I',rom,0x418)[0]==info['program_bytes']
assert hashlib.sha256(rom).hexdigest()==info['sha256']
assert rom[0x2000:0x2006]==bytes.fromhex('4ef90083f000'),'Hard-wired $802000 compatibility entry is not a genuine bootstrap jump'
layout=json.loads((R/'artifacts/dsp/layout.json').read_text());symbols=layout['symbols']
assert symbols['_dsp_entry']==0xf1b100 and symbols['_dsp_bss_end']<0x3e000
assert 0<symbols['_dsp_local_bytes']<=0x1d00
assert len((R/'assets/dsp_game.bin').read_bytes())==layout['image_bytes']
import subprocess
nm=subprocess.check_output(['m68k-linux-gnu-nm','artifacts/program.elf'],cwd=R,text=True)
dsp_addr=int(next(line.split()[0] for line in nm.splitlines() if line.endswith(' dsp_program')),16)
dsp=(R/'assets/dsp_game.bin').read_bytes();off=0x410+dsp_addr-0x10000
assert rom[off:off+len(dsp)]==dsp,'Embedded native DSP image differs from the built game'
mem=json.loads((R/'assets/memory.json').read_text())
assert mem['SCENERY_DRAW_CACHE']+512*96<=mem['SCENERY_COLLISION_CACHE']
assert mem['SCENERY_COLLISION_CACHE']+512*52<=mem['REPLAY_FRAMES']
assert mem['REPLAY_FRAMES']+2048*32<=0x108000<0x10fff0<mem['plane_rotated']

assert len((R/'assets/audio.bin').read_bytes())<=4096
assert 0x2000+len((R/'assets/gpu.bin').read_bytes())<0x10000
# OP-list source regeneration and PAL-safe title/counter placement.
for hz,hud_y in [(50,84),(60,48)]:
    for i in [0,1]:
        op=(R/f'src/gpu/obl{i}_{hz}.bin').read_bytes()
        phrase=struct.unpack_from('>Q',op,0x50)[0]
        assert (phrase&7)==0 and ((phrase>>3)&2047)==hud_y
        assert ((phrase>>14)&1023)==40 and ((phrase>>43)<<3)==0x1ff870
result={'pass':True,'test':'native cartridge and asset structural checks','rom_sha256':info['sha256'],'rom_bytes':len(rom),'asset_bytes':len(b),'tracks':nt,'cars':nc,'meshes':nm,'textures':ntx,'pcm_samples':ns,'converted_inputs':len(manifest['inputs']),'topology':checks,'known_missing_upstream_assets':manifest['missing_upstream_assets'],'native_execution':'68000 cartridge host + real DSP game/physics/audio + requested GPU engine','physics_hz':50,'feature_parity':'INCOMPLETE; this test proves structure, not gameplay. See the separate playability gate.'}
(R/'artifacts').mkdir(exist_ok=True);(R/'artifacts/asset-report.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
