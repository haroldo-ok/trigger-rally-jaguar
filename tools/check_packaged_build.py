#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Extract delivery, build native sources AND emulator source, then boot/drive.

No prebuilt assembler/emulator/game program is reused. Only normal controller
input and read-only output are used for the rebuilt-cartridge probe.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess,sys,tempfile,zipfile
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',nargs='?',type=Path,default=R/'releases/trigger-rally-jaguar-DRIVABLE-source-rom.zip');a=p.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected=sha(R/'releases/trigger-rally-jaguar.j64');(R/'.cache').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='delivery-source-probe-',dir=R/'.cache') as temp:
    with zipfile.ZipFile(a.archive) as z:
        assert z.testzip() is None
        for item in z.infolist():
            rel=Path(item.filename);assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[0]=='trigger-rally-jaguar'
        manifest=json.loads(z.read('trigger-rally-jaguar/PACKAGE_MANIFEST.json'))
        for rel,record in manifest['files'].items():
            data=z.read('trigger-rally-jaguar/'+rel);assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
        z.extractall(temp)
        for item in z.infolist():
            q=Path(temp)/item.filename;stamp=datetime.datetime(*item.date_time,tzinfo=datetime.timezone.utc).timestamp();os.utime(q,(stamp,stamp))
            mode=(item.external_attr>>16)&0o777
            if mode:q.chmod(mode)
    root=Path(temp)/'trigger-rally-jaguar'
    assert not (root/'vendor/lyxass/lyxass').exists() and not list(root.rglob('*.o')) and not list(root.rglob('*.so'))
    assert not (root/'artifacts/program.bin').exists() and not (root/'assets/dsp_game.bin').exists()
    original_info=json.loads((root/'releases/build-info.json').read_text())
    with open(R/'artifacts/packaged-build.log','w') as log:
        subprocess.run(['make','-j4','all'],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
        subprocess.run([sys.executable,'tests/check_assets.py'],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=30,check=True)
    rebuilt=root/'releases/trigger-rally-jaguar.j64';assert sha(rebuilt)==expected,'Fresh package rebuilt a different cartridge'
    info=json.loads((root/'releases/build-info.json').read_text());assert original_info['native_build_inputs_sha256']==info['native_build_inputs_sha256']
    with open(R/'artifacts/packaged-core-build.log','w') as log:subprocess.run(['make','test-core'],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    core=root/'vendor/bin/virtualjaguar_libretro.so';assert core.is_file()
    with open(R/'artifacts/packaged-boot.log','w') as log:
        subprocess.run([sys.executable,'tests/e2e_virtual_jaguar.py','--core',str(core),'--rom',str(rebuilt),'--bios','off','--blitter','accurate','--mode','boot','--timeout','150','--output',str(R/'artifacts/packaged-boot')],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    with open(R/'artifacts/packaged-driving.log','w') as log:
        subprocess.run([sys.executable,'tests/e2e_playability.py','--core',str(core),'--rom',str(rebuilt),'--bios','off','--track','2','--car','0','--finish','--output',str(R/'artifacts/packaged-driving')],cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
    boot=json.loads((R/'artifacts/packaged-boot/report.json').read_text());driving=json.loads((R/'artifacts/packaged-driving/report.json').read_text())
    assert boot['pass'] and driving['pass'] and boot['rom_sha256']==expected==driving['rom_sha256']
    report={'pass':True,'test':'fresh delivery extraction -> source-built toolchains/cartridge/emulator -> actual BIOS-off boot/reset and Base driving/finish','probe_archive_sha256':sha(a.archive),'rebuilt_rom_sha256':sha(rebuilt),'source_inputs_hashes_unchanged':True,'prebuilt_assembler_present':False,'native_objects_present':False,'native_program_binary_present':False,'prebuilt_emulator_present':False,'rebuilt_core_sha256':sha(core),'actual_rom_bios_off_boot_and_reset_pass':True,'actual_rebuilt_source_driving_and_base_finish_pass':True,'identical_to_full_e2e_tested_rom':True,'boot_emulator_frames':boot['emulator_frames'],'driving_emulator_frames':driving['emulator_frames'],'note':'The final ZIP adds only these verification reports/logs/captures. Its source/build/ROM payload is unchanged; the outer ZIP hash changes. The rebuilt Git-less emulator core has its own hash; this probe is not a rerun of every matrix scenario on that core.'}
(R/'artifacts/packaged-build-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
