#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Hash-bound, stock-clock driving suite with specific real-cartridge controls."""
from pathlib import Path
import argparse,concurrent.futures,hashlib,json,os,signal,subprocess,sys,time
R=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--core',type=Path,default=R/'vendor/bin/virtualjaguar_libretro.so');p.add_argument('--rom',type=Path,default=R/'releases/trigger-rally-jaguar.j64');p.add_argument('--output',type=Path,default=R/'artifacts/playability-regression');p.add_argument('--jobs',type=int,default=2);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
started=time.monotonic();original=sha(a.rom);sources={str(f.relative_to(R)):sha(f) for f in sorted((R/'tests').glob('*.py'))};cases=[]
for pal,track,car in [(False,t,c) for t in range(3) for c in range(2)]+[(True,2,c) for c in range(2)]:
    name=('pal' if pal else 'ntsc')+f'-track-{track}-car-{car}';out=a.output/name
    cmd=[sys.executable,str(R/'tests/e2e_playability.py'),'--core',str(a.core.resolve()),'--rom',str(a.rom.resolve()),'--track',str(track),'--car',str(car),'--bios','off','--output',str(out.resolve()),'--timeout','180']
    if pal:cmd+=['--pal']
    if track==2 and car==0:cmd+=['--finish']
    cases.append((name,out,cmd,(),original))
for kind,expected in [('no-acceleration',('ACCELERATOR_DID_NOT_MOVE_CAR',)),('slow-racing',('SIMULATION_NOT_RUNNING_IN_REALTIME','COMPLETED_GAME_FPS_TOO_LOW','VISIBLE_GAME_FRAME_GAP_TOO_LONG'))]:
    fault=R/'.cache'/('playability-'+kind+'.j64');out=a.output/('negative-'+kind);out.mkdir(parents=True,exist_ok=True)
    with open(out/'build.log','w') as log:subprocess.run([sys.executable,str(R/'tests/make_fault_rom.py'),'--kind',kind,'--rom',str(a.rom.resolve()),'--output',str(fault)],cwd=R,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    cmd=[sys.executable,str(R/'tests/e2e_playability.py'),'--core',str(a.core.resolve()),'--rom',str(fault),'--output',str(out.resolve()),'--bios','off','--timeout','180']
    cases.append(('negative-'+kind,out,cmd,expected,sha(fault)))
def worker(case):
    name,out,cmd,expected,tested_hash=case;out.mkdir(parents=True,exist_ok=True)
    with open(out/'runner.log','w') as log:
        child=subprocess.Popen(cmd,cwd=R,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=child.wait(timeout=200)
        except subprocess.TimeoutExpired:
            code=124
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
    try:d=json.loads((out/'report.json').read_text())
    except (OSError,ValueError):d={}
    ok=code==0 and d.get('pass') is True if not expected else code not in (0,124) and d.get('pass') is False and any(e in (d.get('error') or '') for e in expected)
    ok=ok and d.get('rom_sha256')==tested_hash and d.get('core_sha256')==sha(a.core)
    report_path=str((out/'report.json').relative_to(R)) if out.is_relative_to(R) else str(out/'report.json')
    row={'name':name,'pass':ok,'tested_rom_sha256':tested_hash,'worker_exit_code':code,'expected_errors':list(expected),'observed_error':d.get('error'),'report':report_path};print(('PASS ' if ok else 'FAIL ')+name,flush=True);return row
with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:results=list(pool.map(worker,cases))
unchanged=sha(a.rom)==original;current={str(f.relative_to(R)):sha(f) for f in sorted((R/'tests').glob('*.py'))}
report={'pass':all(r['pass'] for r in results) and unchanged and current==sources,'test':'eight stock-clock driving configurations, genuine Base course completion, native zero-engine-power and slow-racing controls','rom_sha256':original,'core_sha256':sha(a.core),'normal_configurations':8,'specific_negative_controls':2,'rom_unchanged_by_tests':unchanged,'test_sources_unchanged_during_run':current==sources,'test_sources_sha256':sources,'cases':results,'wall_seconds':time.monotonic()-started,'coverage':'All three tracks / both cars under NTSC; both cars on Base under PAL. Base/car0 is genuinely finished in NTSC and PAL; no replay-as-finish shortcut. Not all paths/hardware or full original feature parity.'}
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(('PASS' if report['pass'] else 'FAIL')+' playability suite',flush=True);raise SystemExit(0 if report['pass'] else 1)
