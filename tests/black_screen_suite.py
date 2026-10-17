#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Release-gating Virtual Jaguar black-screen regression (desktop AND core).

Every normal case uses a fresh emulator process and actual delivered cartridge.
Negative controls are real modified cartridges, not fabricated video/RAM state.
An expected failure counts only when the specific intended watchdog detects it;
a missing emulator/dependency/crash does not count as a successful control.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=R/'releases/trigger-rally-jaguar.j64')
    p.add_argument('--core',type=Path,default=R/'vendor/bin/virtualjaguar_libretro.so')
    p.add_argument('--emulator',type=Path,default=Path(shutil.which('virtualjaguar') or '/usr/bin/virtualjaguar'))
    p.add_argument('--output',type=Path,default=R/'artifacts/black-screen-regression')
    p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--smoke',action='store_true',help='Boot/menu/reset matrix, no desktop countdown/racing. Not full gameplay coverage.')
    a=p.parse_args();a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'report.json').unlink(missing_ok=True)
    if not 1<=a.jobs<=4:p.error('--jobs must be 1..4')
    for tool in ['Xvfb','xdotool','import','xset','m68k-linux-gnu-gcc','m68k-linux-gnu-objcopy']:
        if not shutil.which(tool):p.error('Required dependency missing (not skipped): '+tool)
    if not a.emulator.is_file() or not a.core.is_file():p.error('Both desktop Virtual Jaguar and its test core are required')
    started=time.monotonic();rom_sha=sha(a.rom);core_sha=sha(a.core)
    script_hashes={str(f.relative_to(R)):sha(f) for f in (R/'tests').glob('*.py')}
    faults=R/'.cache/black-screen-controls';faults.mkdir(parents=True,exist_ok=True)
    for kind in ['entry','black-after-boot','freeze-after-boot']:
        with open(a.output/('build-control-'+kind+'.log'),'w') as log:
            q=subprocess.run([sys.executable,str(R/'tests/make_fault_rom.py'),'--rom',str(a.rom.resolve()),'--kind',kind,'--output',str(faults/(kind+'.j64'))],cwd=R,stdout=log,stderr=subprocess.STDOUT)
        if q.returncode:
            raise SystemExit('Negative-control build failed; see '+str(a.output/('build-control-'+kind+'.log')))
    cases=[]
    def core_case(name,rom,bios,standard,blitter='accurate',expected=None):
        out=a.output/name
        cmd=[sys.executable,str(R/'tests/e2e_virtual_jaguar.py'),'--rom',str(rom.resolve()),'--core',str(a.core.resolve()),'--bios',bios,'--blitter',blitter,'--mode','boot','--timeout','150','--output',str(out)]
        if standard=='pal':cmd.append('--pal')
        cases.append({'name':name,'frontend':'core','rom':rom,'command':cmd,'output':out,'expected_failure':expected})
    def gui_case(name,rom,bios,standard,mode='boot',expected=None):
        out=a.output/name
        cmd=[sys.executable,str(R/'tests/e2e_desktop_virtual_jaguar.py'),'--rom',str(rom.resolve()),'--emulator',str(a.emulator.resolve()),'--bios',bios,'--standard',standard,'--mode',mode,'--timeout',('90' if expected else '1000'),'--output',str(out)]
        cases.append({'name':name,'frontend':'desktop','rom':rom,'command':cmd,'output':out,'expected_failure':expected})
    # Start the longer actual-desktop gameplay test first, overlapping short cases.
    gui_case('desktop-ntsc-bios-off',a.rom,'off','ntsc','boot' if a.smoke else 'full')
    for standard in ['ntsc','pal']:
        for bios in ['on','off']:
            for blitter in ['accurate','fast']:
                core_case('core-'+standard+'-bios-'+bios+'-'+blitter,a.rom,bios,standard,blitter)
    for standard,bios in [('ntsc','on'),('pal','on'),('pal','off'),('ntsc','default')]:
        gui_case('desktop-'+standard+'-bios-'+bios,a.rom,bios,standard)
    for bios in ['on','off']:
        core_case('negative-core-entry-bios-'+bios,faults/'entry.j64',bios,'ntsc',expected='Timed out waiting in boot')
    gui_case('negative-desktop-entry',faults/'entry.j64','off','ntsc',expected='BLACK_BOOT')
    gui_case('negative-desktop-black-after-boot',faults/'black-after-boot.j64','off','ntsc',mode='watchdog',expected='BLACK_SCREEN')
    gui_case('negative-desktop-freeze-after-boot',faults/'freeze-after-boot.j64','off','ntsc',mode='watchdog',expected='FROZEN_GAME')

    def execute(c):
        c['output'].mkdir(parents=True,exist_ok=True)
        with open(c['output']/'runner.log','w') as log:
            q=subprocess.run(c['command'],cwd=R,stdout=log,stderr=subprocess.STDOUT)
        try:d=json.loads((c['output']/'report.json').read_text())
        except (FileNotFoundError,json.JSONDecodeError):d={'pass':False,'error':'Worker produced no valid report'}
        expected=c['expected_failure']
        if expected:
            passed=q.returncode!=0 and d.get('pass') is False and expected in (d.get('error') or '')
            if 'after-boot' in c['name']:passed=passed and len(d.get('checks',[]))>=1
        else:
            passed=q.returncode==0 and d.get('pass') is True
        passed=passed and d.get('rom_sha256')==sha(c['rom'])
        result={'name':c['name'],'frontend':c['frontend'],'pass':passed,'expected_failure':expected,'worker_pass':d.get('pass'),'worker_exit_code':q.returncode,'error':d.get('error'),'report':str((c['output']/'report.json').relative_to(R)),'tested_rom_sha256':d.get('rom_sha256')}
        print(('PASS' if passed else 'FAIL')+' '+c['name']+(' (specific fault correctly detected)' if expected else ''),flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:
        results=list(pool.map(execute,cases))
    unchanged=rom_sha==sha(a.rom)
    tests_unchanged=all(sha(R/f)==h for f,h in script_hashes.items())
    passed=all(c['pass'] for c in results) and unchanged and tests_unchanged
    report={'pass':passed,'test':'actual Virtual Jaguar desktop/core black-screen release gate','mode':'smoke' if a.smoke else 'desktop gameplay plus boot/reset matrix','rom_sha256':rom_sha,'core_sha256':core_sha,'desktop_emulator_sha256':sha(a.emulator),'normal_configurations':sum(c['expected_failure'] is None for c in cases),'negative_controls':sum(c['expected_failure'] is not None for c in cases),'cases':results,'rom_unchanged_by_tests':unchanged,'test_sources_unchanged_during_run':tests_unchanged,'test_sources_sha256':script_hashes,'wall_seconds':time.monotonic()-started,'limitations':['Finite tested configurations; cannot guarantee a program will never freeze.','Smoke mode omits desktop racing; a full desktop report is separately required by the release packer.','No full Trigger Rally conversion, acceptable frame rate or physical Jaguar compatibility claim.']}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(('PASS' if passed else 'FAIL')+' black-screen suite; '+str(a.output/'report.json'),flush=True)
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
