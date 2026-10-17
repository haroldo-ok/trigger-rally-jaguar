#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package the gated drivable cartridge, preferred sources and current evidence.

Uses the compact source distribution (no prebuilt emulator, objects, unit/fault
cartridges or historical reports). All source, ROM and evidence bytes are hashed.
"""
from pathlib import Path
import hashlib,json,stat,subprocess,sys,zipfile
from verify_release import verify,need
R=Path(__file__).resolve().parents[1];d=verify()
summary=json.loads((R/'releases/port-summary.json').read_text());need(summary['rom_sha256']==d['rom_sha256'] and summary.get('drivable_racing_verified'),'run make_report.py first')
subprocess.run([sys.executable,str(R/'tools/make_source_archive.py')],cwd=R,check=True)
source=R/'releases/trigger-rally-jaguar-sources.zip';files={};modes={}
with zipfile.ZipFile(source) as z:
    need(z.testzip() is None,'source ZIP CRC failed')
    for item in z.infolist():
        name=Path(item.filename);need(name.parts[0]=='trigger-rally-jaguar' and '..' not in name.parts and not name.is_absolute(),'unsafe source entry')
        if item.is_dir():continue
        rel=Path(*name.parts[1:]).as_posix();files[rel]=z.read(item);modes[rel]=(item.external_attr>>16)&0o777 or 0o644
for name in ['trigger-rally-jaguar.j64','build-info.json','ROM.sha256','port-summary.json','port-report.html','SOURCES.sha256']:
    p=R/'releases'/name;files['releases/'+name]=p.read_bytes();modes['releases/'+name]=0o644
video_meta=R/'releases/base-course-playthrough.json'
if video_meta.is_file():
    video=json.loads(video_meta.read_text());movie=R/'releases/base-course-playthrough.mp4'
    need(video.get('rom_sha256')==d['rom_sha256'] and video.get('actual_emulator_capture') and movie.is_file() and hashlib.sha256(movie.read_bytes()).hexdigest()==video['video_sha256'],'stale/invalid playthrough video')
    for name in ['base-course-playthrough.mp4','base-course-playthrough.json']:
        files['releases/'+name]=(R/'releases'/name).read_bytes();modes['releases/'+name]=0o644
selected=set(d['evidence'])
for name in list(selected):
    parent=Path(name).parent
    if parent!=Path('artifacts'):
        selected.update(str(p.relative_to(R)) for p in (R/parent).rglob('*') if p.is_file() and p.suffix in {'.json','.jsonl','.png','.log'})
for name in ['artifacts/native-clean-build-1.log','artifacts/native-clean-build-2.log','artifacts/hud-decoder-report.json','artifacts/playability-suite.log','artifacts/black-screen-suite.log']:
    if (R/name).is_file():selected.add(name)
proof=R/'artifacts/packaged-build-report.json'
if proof.exists() and json.loads(proof.read_text()).get('rebuilt_rom_sha256')==d['rom_sha256']:
    selected.add('artifacts/packaged-build-report.json')
    for name in ['artifacts/packaged-build.log','artifacts/packaged-core-build.log','artifacts/packaged-boot.log','artifacts/packaged-driving.log']:
        if (R/name).is_file():selected.add(name)
    for folder in ['packaged-boot','packaged-driving']:
        selected.update(str(p.relative_to(R)) for p in (R/'artifacts'/folder).rglob('*') if p.is_file() and p.suffix in {'.json','.jsonl','.png','.log'})
for rel in sorted(selected):
    p=R/rel;need(p.is_file(),'evidence missing: '+rel);files[rel]=p.read_bytes();modes[rel]=0o644
need([n for n in files if n.endswith('.j64')]==['releases/trigger-rally-jaguar.j64'],'unit/fault/old cartridge in delivery')
need(not any(n.endswith(('.so','.o','.elf','.exe')) for n in files),'prebuilt emulator/object leaked into source delivery')
manifest={'status':summary['status'],'only_cartridge':'releases/trigger-rally-jaguar.j64','rom_sha256':d['rom_sha256'],'source_archive_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'content_rights':summary['content_rights'],'negative_worker_reports_are_expected_failures':True,'emulator_executable_included':False,'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(files.items())}}
output=R/'releases/trigger-rally-jaguar-DRIVABLE-source-rom.zip';temp=output.with_suffix('.zip.tmp')
with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,data in sorted(files.items()):
        item=zipfile.ZipInfo('trigger-rally-jaguar/'+name,(2000,1,1,0,0,0));item.create_system=3;item.external_attr=(stat.S_IFREG|modes[name])<<16
        item.compress_type=zipfile.ZIP_STORED if name.endswith('.gz') else zipfile.ZIP_DEFLATED;z.writestr(item,data)
    item=zipfile.ZipInfo('trigger-rally-jaguar/PACKAGE_MANIFEST.json',(2000,1,1,0,0,0));item.compress_type=zipfile.ZIP_DEFLATED;z.writestr(item,json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(temp) as z:
    need(z.testzip() is None,'delivery CRC failed')
    for name,record in manifest['files'].items():
        data=z.read('trigger-rally-jaguar/'+name);need(len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],'entry hash mismatch: '+name)
temp.replace(output);digest=hashlib.sha256(output.read_bytes()).hexdigest();(R/'releases/PACKAGE.sha256').write_text(digest+'  '+output.name+'\n')
print(json.dumps({'archive':str(output),'bytes':output.stat().st_size,'files':len(files)+1,'sha256':digest,'rom_sha256':d['rom_sha256'],'gated_driving_and_actual_desktop_required':True,'only_current_game_cartridge':True,'every_entry_verified':True},indent=2))
