#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Causal regression for the exact historical universal-header boot defect.

A copy of the CURRENT game retains its valid signed loader/code/assets but
changes only the universal-header PC to invalid DSP code at $802010.
The current cartridge has a genuine compatibility trampoline at $802000, so
that formerly bad entry is now deliberately safe as well. It MUST boot with BIOS on
and MUST be rejected with BIOS off, in BOTH real frontends. This detects a
frontend accidentally forcing BIOS on for every nominal configuration.

Malformed native entry can make old desktop Virtual Jaguar exit immediately
(including status 0) or SIGSEGV, instead of staying black. Record the actual
native process exit before cleanup, with no successful native boot checkpoint;
a generic dependency, xdotool, Qt startup or Python-worker error alone is NOT proof.
The five separate suite watchdog controls remain strictly reason-matched.
"""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,os,shutil,signal,struct,subprocess,sys,traceback
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--core',type=Path,default=R/'vendor/bin/virtualjaguar_libretro.so')
p.add_argument('--emulator',type=Path,default=Path(shutil.which('virtualjaguar') or '/usr/bin/virtualjaguar'))
p.add_argument('--desktop-worker',action='store_true',help=argparse.SUPPRESS)
p.add_argument('--worker-bios',choices=['on','off'],help=argparse.SUPPRESS)
p.add_argument('--worker-output',type=Path,help=argparse.SUPPRESS)
p.add_argument('--fault-rom',type=Path,help=argparse.SUPPRESS)
a=p.parse_args()
sha=lambda x:hashlib.sha256(x).hexdigest()

if a.desktop_worker:
    # The SAME unchanged desktop E2E class, with one additional read-only
    # diagnostic of the actual native emulator's return code before cleanup.
    sys.path.insert(0,str(R/'tests'))
    from e2e_desktop_virtual_jaguar import DesktopRun
    settings=argparse.Namespace(rom=a.fault_rom,emulator=a.emulator,bios=a.worker_bios,standard='ntsc',mode='boot',output=a.worker_output,timeout=120)
    run=None;passed=False;error=None
    try:run=DesktopRun(settings);run.run();passed=True
    except Exception as exc:error=type(exc).__name__+': '+str(exc);traceback.print_exc()
    finally:
        if run:
            result=run.report(passed,error)
            result['native_emulator_exit_before_cleanup']=run.gui.poll() if hasattr(run,'gui') else None
            (settings.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
            run.close()
    raise SystemExit(0 if passed else 1)

out=R/'artifacts/bios-path-regression';out.mkdir(parents=True,exist_ok=True)
(out/'report.json').unlink(missing_ok=True)
base=(R/'releases/trigger-rally-jaguar.j64').read_bytes();bad=bytearray(base)
assert struct.unpack_from('>I',bad,0x404)[0]==0x83f000
struct.pack_into('>I',bad,0x404,0x802010)
assert base[:0x404]==bad[:0x404] and base[0x408:]==bad[0x408:]
fault=R/'.cache/historical-bios-entry.j64';fault.parent.mkdir(exist_ok=True);fault.write_bytes(bad)
cases=[]
for frontend in ['core','desktop']:
    for bios in ['on','off']:
        name=frontend+'-bios-'+bios;dest=out/name
        if frontend=='core':
            command=[sys.executable,str(R/'tests/e2e_virtual_jaguar.py'),'--rom',str(fault),'--bios',bios,'--mode','boot','--timeout','120','--output',str(dest),'--core',str(a.core.resolve()),'--blitter','accurate']
        else:
            command=[sys.executable,str(Path(__file__).resolve()),'--desktop-worker','--worker-bios',bios,'--worker-output',str(dest),'--fault-rom',str(fault),'--emulator',str(a.emulator.resolve())]
        cases.append((name,bios,frontend,dest,command))

def run(case):
    name,bios,frontend,dest,command=case;dest.mkdir(parents=True,exist_ok=True)
    timed_out=False
    with open(dest/'runner.log','w') as log:
        child=subprocess.Popen(command,cwd=R,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=child.wait(timeout=150)
        except subprocess.TimeoutExpired:code=124;timed_out=True
        finally:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
    try:d=json.loads((dest/'report.json').read_text())
    except (OSError,ValueError):d={}
    expected=None if bios=='on' else ('Timed out waiting in boot' if frontend=='core' else 'BLACK_BOOT or observed native emulator termination before native boot (status 0 / SIGSEGV)')
    if bios=='on':good=code==0 and d.get('pass') is True
    elif frontend=='core':good=code!=0 and d.get('pass') is False and 'Timed out waiting in boot' in (d.get('error') or '')
    else:
        native_exit=d.get('native_emulator_exit_before_cleanup')
        terminated_before_boot=native_exit in (0,-signal.SIGSEGV) and isinstance(native_exit,int) and not d.get('checks')
        rejected='BLACK_BOOT' in (d.get('error') or '') or terminated_before_boot
        good=code!=0 and d.get('pass') is False and rejected
    good=good and not timed_out and d.get('rom_sha256')==sha(bad)
    result={'name':name,'pass':good,'bios':bios,'frontend':frontend,'expected_worker_pass':bios=='on','worker_pass':d.get('pass'),'worker_exit_code':code,'expected_error':expected,'observed_error':d.get('error'),'native_emulator_exit_before_cleanup':d.get('native_emulator_exit_before_cleanup'),'report':str((dest/'report.json').relative_to(R))}
    print(('PASS' if good else 'FAIL')+' historical-header '+name,flush=True);return result

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,cases))
unchanged=base==(R/'releases/trigger-rally-jaguar.j64').read_bytes()
inputs=['tools/check_bios_path_regression.py','tests/vj.py','tests/e2e_virtual_jaguar.py','tests/e2e_desktop_virtual_jaguar.py']
report={'pass':all(c['pass'] for c in results) and unchanged,'test':'wrong universal-header entry (past the safe compatibility trampoline): BIOS on succeeds and BIOS off is rejected, BOTH real Virtual Jaguar frontends','base_game_rom_sha256':sha(base),'fault_rom_sha256':sha(bad),'only_header_pc_changed':True,'released_rom_unchanged':unchanged,'source_sha256':{f:sha((R/f).read_bytes()) for f in inputs},'cases':results,'desktop_note':'Malformed native entry was observed to make desktop 2.1.3 exit with status 0 before boot, rather than stay black. Specific BLACK_BOOT, or recorded native-app status 0/SIGSEGV BEFORE any native boot checkpoint, is accepted for this causal boot-failure probe only. A generic worker/input/dependency error without that native exit is not accepted. Normal BIOS-off and same-fault BIOS-on passes provide healthy controls; the five separate watchdog controls still require their precise watchdog errors.'}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(('PASS' if report['pass'] else 'FAIL')+' BIOS-path regression',flush=True)
raise SystemExit(0 if report['pass'] else 1)
