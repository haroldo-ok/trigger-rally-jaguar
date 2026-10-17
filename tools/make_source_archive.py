#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Package editable port/build/test sources and the data needed to rebuild.

No game cartridge, emulator executable, build outputs or historical release
reports are included. The upstream emulator snapshot retains its build sources
but drops optional website artwork and precompiled test cartridges/disc images.
The original vendored archive is not modified.
"""
from pathlib import Path,PurePosixPath
import copy,gzip,hashlib,io,json,stat,tarfile,zipfile

R=Path(__file__).resolve().parents[1]
EPOCH=(2000,1,1,0,0,0)
sha=lambda b:hashlib.sha256(b).hexdigest()
ROOT_FILES={'README.md','Makefile','requirements.txt','LICENSE','LICENSES.md','.gitignore'}
SOURCE_DIRS={'src','assets','tools','tests','docs','licenses','vendor','.github'}
EXCLUDED_DIRS={'.git','.cache','.venv','__pycache__','node_modules','bin'}
BUILD_EXT={'.o','.obj','.P','.d','.dep','.elf','.map','.sym','.pyc','.so','.dll','.dylib','.exe','.a','.zip','.tmp'}
CORE_BINARY_EXT={'.j64','.jag','.rom','.abs','.cof','.coff','.elf','.o','.obj','.so','.dll','.dylib','.exe','.a','.chd','.zip','.7z'}
core_path=R/'vendor/virtualjaguar-libretro-source.tar.gz'
original=core_path.read_bytes();trimmed=io.BytesIO();removed=[];retained=0;code_count=0
code_ext={'.c','.cpp','.h','.hpp','.s','.S','.inc','.asm','.mk','.py','.sh','.js','.cmake','.glsl','.vert','.frag'}
with tarfile.open(fileobj=io.BytesIO(original),mode='r:gz') as source:
    with gzip.GzipFile(fileobj=trimmed,mode='wb',mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as target:
            for member in sorted(source.getmembers(),key=lambda m:m.name):
                path=PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe upstream archive path')
                relative=PurePosixPath(*path.parts[1:])
                artwork=str(relative).startswith('site/thumbnails/') or (str(relative).startswith('docs/site/') and path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.gif'})
                omit=artwork or path.suffix.lower() in CORE_BINARY_EXT or any(p in {'.git','__pycache__','node_modules'} for p in path.parts)
                if omit:
                    if member.isfile():removed.append(member.name)
                    continue
                item=copy.copy(member);item.uid=item.gid=0;item.uname=item.gname='';item.mtime=946684800;item.pax_headers={}
                if member.isfile():
                    data=source.extractfile(member).read();target.addfile(item,io.BytesIO(data));retained+=1
                    if path.suffix in code_ext or path.name.startswith(('Makefile','CMakeLists','LICENSE','COPYING')):code_count+=1
                elif member.isdir() or member.issym() or member.islnk():target.addfile(item)
core_bytes=trimmed.getvalue()
files={};modes={}
for base in sorted(SOURCE_DIRS):
    for p in sorted((R/base).rglob('*')):
        if not p.is_file() or p.is_symlink():continue
        rel=p.relative_to(R);name=rel.as_posix()
        if any(part in EXCLUDED_DIRS for part in rel.parts):continue
        if p.suffix in BUILD_EXT or p.suffix.lower() in {'.j64','.jag','.rom','.abs','.cof','.chd'}:continue
        if name=='vendor/lyxass/lyxass' or p.name in {'make.dep','make.dependencies'}:continue
        if name in {'assets/gpu.bin','assets/audio.bin','assets/dsp_game.bin','src/dsp/image.h'} or (rel.parent==Path('src/gpu') and p.name.startswith('obl') and p.suffix=='.bin'):continue
        files[name]=core_bytes if p==core_path else p.read_bytes();modes[name]=stat.S_IMODE(p.stat().st_mode)
for name in sorted(ROOT_FILES):files[name]=(R/name).read_bytes();modes[name]=stat.S_IMODE((R/name).stat().st_mode)
required={'README.md','src/main.c','src/host.c','src/dsp/start.s','src/dsp/float_fast.s','tools/patches/vbcc-jrisc-binary32.patch','vendor/jrisc/vbcc.tar.gz','vendor/jrisc/vasm.tar.gz','vendor/jrisc/vlink.tar.gz','src/cartboot.S','src/gpu/rally.js','src/boot.js','src/boot.XXX','src/font8x8.bin','assets/assets.bin','tests/black_screen_suite.py','.github/workflows/virtual-jaguar-e2e.yml','vendor/virtualjaguar-libretro-source.tar.gz'}
assert required<=files.keys(),required-files.keys()
assert all(not name.endswith(('.j64','.so','.o')) for name in files)
manifest={
 'kind':'native port/build/test sources with required converted data and signed-loader input',
 'status':'Experimental drivable racing; full original feature/fidelity conversion remains INCOMPLETE',
 'prebuilt_game_or_emulator_included':False,'historical_release_reports_included':False,
 'build_inputs_retained':['converted asset bank and IDs','bitmap font','pre-signed loader with corresponding editable source'],
 'emulator_source_snapshot':{'upstream_revision':'6bf3574c1a98ccd57719ff6b822122017b8e5942','original_archive_sha256':sha(original),'packaged_archive_sha256':sha(core_bytes),'retained_regular_files':retained,'retained_code_build_license_files':code_count,'removed_optional_artwork_or_precompiled_test_data':removed,'retained_file_contents_unchanged':True},
 'files':{name:{'bytes':len(data),'sha256':sha(data)} for name,data in sorted(files.items())},
}
output=R/'releases/trigger-rally-jaguar-sources.zip';output.parent.mkdir(exist_ok=True);temporary=output.with_suffix('.zip.tmp')
with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,data in sorted(files.items()):
        item=zipfile.ZipInfo('trigger-rally-jaguar/'+name,EPOCH);item.create_system=3;item.external_attr=(stat.S_IFREG|modes[name])<<16
        item.compress_type=zipfile.ZIP_STORED if name.endswith('.gz') else zipfile.ZIP_DEFLATED
        z.writestr(item,data)
    item=zipfile.ZipInfo('trigger-rally-jaguar/SOURCE_MANIFEST.json',EPOCH);item.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(item,json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
with zipfile.ZipFile(temporary) as z:
    assert z.testzip() is None
    assert z.read('trigger-rally-jaguar/README.md')==(R/'README.md').read_bytes()
    for name,data in files.items():assert z.read('trigger-rally-jaguar/'+name)==data,name
    # Also inspect the nested source snapshot, not just top-level ZIP names.
    with tarfile.open(fileobj=io.BytesIO(z.read('trigger-rally-jaguar/vendor/virtualjaguar-libretro-source.tar.gz')),mode='r:gz') as t:
        assert not any(PurePosixPath(m.name).suffix.lower() in CORE_BINARY_EXT for m in t.getmembers() if m.isfile())
temporary.replace(output)
digest=sha(output.read_bytes());(R/'releases/SOURCES.sha256').write_text(digest+'  '+output.name+'\n')
print(json.dumps({'archive':str(output),'bytes':output.stat().st_size,'files':len(files)+1,'sha256':digest,'updated_readme_included':True,'prebuilt_game_or_emulator_included':False,'trimmed_emulator_build_sources_bytes':len(core_bytes),'every_entry_verified':True},indent=2))
