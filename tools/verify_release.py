#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Refuse a release without current, exact-cartridge Virtual Jaguar evidence.

This is a consistency/release gate, not a cryptographic attestation that tests
were honestly run. Reports and code remain available for independent reruns.
"""
from pathlib import Path
import hashlib,json,sys
from build_inputs import fingerprint
R=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def need(ok,message):
    if not ok:raise RuntimeError('RELEASE BLOCKED: '+message)
def read(path):
    p=R/path
    need(p.is_file(),'missing '+str(path)+'; run make test and tools/check_reproducibility.py first')
    return json.loads(p.read_text())

def verify():
    rom=R/'releases/trigger-rally-jaguar.j64';rom_hash=sha(rom)
    info=read('releases/build-info.json')
    need(info['sha256']==rom_hash and rom.stat().st_size==4194304,'ROM/build-info mismatch')
    need(info.get('native_build_inputs_sha256')==fingerprint(),'native source/build inputs changed since this ROM was packed; rebuild and retest')
    need((R/'releases/ROM.sha256').read_text()==rom_hash+'  '+rom.name+'\n','ROM checksum file is stale')
    core_hash=sha(R/'vendor/bin/virtualjaguar_libretro.so')
    suite=read('artifacts/black-screen-regression/report.json')
    need(suite.get('pass') is True,'black-screen matrix did not pass')
    need(suite.get('mode')=='desktop gameplay plus boot/reset matrix','smoke mode cannot authorize a release; run the full default suite')
    need(suite['rom_sha256']==rom_hash and suite['core_sha256']==core_hash,'matrix tested a different ROM/core')
    need(suite.get('rom_unchanged_by_tests') and suite.get('test_sources_unchanged_during_run'),'test inputs changed during the run')
    current={str(f.relative_to(R)):sha(f) for f in (R/'tests').glob('*.py')}
    need(suite.get('test_sources_sha256')==current,'test sources changed since the matrix ran')
    expected={'desktop-ntsc-bios-off','desktop-ntsc-bios-on','desktop-pal-bios-on','desktop-pal-bios-off','desktop-ntsc-bios-default'}
    expected.update('core-'+v+'-bios-'+b+'-'+bl for v in ['ntsc','pal'] for b in ['on','off'] for bl in ['accurate','fast'])
    controls={'negative-core-entry-bios-on':'Timed out waiting in boot','negative-core-entry-bios-off':'Timed out waiting in boot','negative-desktop-entry':'BLACK_BOOT','negative-desktop-black-after-boot':'BLACK_SCREEN','negative-desktop-freeze-after-boot':'FROZEN_GAME'}
    need(suite.get('normal_configurations')==13 and suite.get('negative_controls')==5,'incomplete matrix/control counts')
    need(len(suite['cases'])==18 and {c['name'] for c in suite['cases']}==expected|set(controls),'missing/duplicated matrix configurations')
    evidence=['artifacts/black-screen-regression/report.json']
    full_desktop=None;desktop_path=None
    for case in suite['cases']:
        need(case.get('pass') is True,'case failed: '+case['name'])
        worker=read(case['report']);evidence.append(case['report'])
        need(case['tested_rom_sha256']==worker['rom_sha256'],'worker/report hash mismatch: '+case['name'])
        if case['name'] in controls:
            error=controls[case['name']]
            need(worker.get('pass') is False and case['worker_exit_code']!=0 and error in (worker.get('error') or ''),'negative control failed for an unrelated reason: '+case['name'])
            need(worker['rom_sha256']!=rom_hash,'negative control used the released ROM')
            if 'after-boot' in case['name']:need(len(worker.get('checks',[]))>=1,'post-boot control never booted')
        else:
            need(worker.get('pass') is True and case['worker_exit_code']==0 and worker['rom_sha256']==rom_hash,'normal case did not test the delivered cartridge')
            parts=case['name'].split('-');standard=parts[1];bios=parts[3]
            need(worker['bios']==bios,'wrong BIOS path: '+case['name'])
            if parts[0]=='core':
                need(worker['core_sha256']==core_hash and worker['video_standard']==standard.upper() and worker['blitter']==parts[4],'wrong core settings')
                need(worker.get('isolated_saved_state') and len(worker['checks'])>=4,'missing core reset/soak coverage')
            else:
                command=worker.get('command') or []
                need((('--bios' in command) if bios=='on' else ('--no-bios' in command) if bios=='off' else ('--bios' not in command and '--no-bios' not in command)),'desktop command did not use the requested BIOS path')
                need(worker['emulator_sha256']==suite['desktop_emulator_sha256'] and worker['standard']==standard,'desktop binary/video mismatch')
                need(worker.get('fresh_home_and_xdg_config') and len(worker['checks'])>=10,'missing desktop clean-profile/reset/selection coverage')
                if worker['mode']=='full' and bios=='off' and standard=='ntsc':full_desktop=worker;desktop_path=case['report']
    need(full_desktop is not None,'full desktop gameplay must pass inside the current matrix')
    need(full_desktop.get('pass') is True and full_desktop.get('mode')=='full' and full_desktop['rom_sha256']==rom_hash,'a full desktop gameplay pass for the exact ROM is required, even with --smoke')
    need(full_desktop.get('fresh_home_and_xdg_config') and full_desktop['emulator_sha256']==suite['desktop_emulator_sha256'],'full desktop settings/binary mismatch')
    need(full_desktop['bios']=='off' and full_desktop['standard']=='ntsc' and len(full_desktop['checks'])>=15,'full desktop coverage is incomplete')
    full_core={}
    for bios,path in [('on','artifacts/e2e-ntsc/report.json'),('off','artifacts/e2e-ntsc-bios-off/report.json')]:
        d=read(path);evidence.append(path)
        need(d.get('pass') is True and d.get('mode')=='full' and d['rom_sha256']==rom_hash and d['core_sha256']==core_hash,'full core '+bios+' evidence is stale/failed')
        need(d['bios']==bios and d['blitter']=='accurate' and d['video_standard']=='NTSC' and len(d['checks'])>=21,'both accurate full BIOS paths/reset coverage are required')
        full_core[bios]=d
    causal=read('artifacts/bios-path-regression/report.json')
    need(causal.get('pass') is True and causal.get('base_game_rom_sha256')==rom_hash,'historical wrong-header/real BIOS-path regression missing or stale')
    need(causal.get('only_header_pc_changed') and causal.get('released_rom_unchanged'),'historical fault must not change the delivered cartridge')
    need({c['name'] for c in causal['cases']}=={'core-bios-on','core-bios-off','desktop-bios-on','desktop-bios-off'} and len(causal['cases'])==4,'missing BIOS-causal controls')
    for c in causal['cases']:
        need(c['pass'] is True and c['worker_pass'] is (c['bios']=='on'),'BIOS-path regression did not prove on succeeds / off fails')
        worker=read(c['report']);evidence.append(c['report'])
        need(worker['rom_sha256']==causal['fault_rom_sha256'] and worker['bios']==c['bios'],'wrong historical control cartridge/path')
        if c['frontend']=='core':need(worker['core_sha256']==core_hash,'historical control used a different core')
        else:need(worker['emulator_sha256']==suite['desktop_emulator_sha256'],'historical control used a different desktop emulator')
        if c['bios']=='on':need(worker['pass'] is True,'valid signed loader must still boot the faulty-HLE-header copy')
        elif c['frontend']=='core':need(worker['pass'] is False and 'Timed out waiting in boot' in (worker.get('error') or ''),'wrong core historical-fault rejection')
        else:need(worker['pass'] is False and ('BLACK_BOOT' in (worker.get('error') or '') or (worker.get('native_emulator_exit_before_cleanup') in (0,-11) and isinstance(worker.get('native_emulator_exit_before_cleanup'),int) and not worker.get('checks'))),'unrelated desktop failure is not a historical control pass')
    for path,value in causal['source_sha256'].items():need(sha(R/path)==value,'historical-path test source changed')
    evidence.append('artifacts/bios-path-regression/report.json')
    assets=read('artifacts/asset-report.json');math=read('artifacts/math-report.json');build=read('artifacts/build-reproducibility.json')
    need(assets.get('pass') is True and assets['rom_sha256']==rom_hash,'stale or failed structure checks')
    need(math.get('pass') is True and math['core_sha256']==core_hash and math['operations']>=4096,'arithmetic check is missing/failed')
    need(build.get('pass') is True and build.get('clean_builds_byte_identical') is True and build['rom_sha256_before']==rom_hash==build['rom_sha256_after'],'clean source rebuild is stale/failed')
    driving=read('artifacts/playability-regression/report.json')
    need(driving.get('pass') is True and driving.get('rom_sha256')==rom_hash and driving.get('core_sha256')==core_hash,'missing/stale/failed real-time driving suite')
    need(driving.get('normal_configurations')==8 and driving.get('specific_negative_controls')==2,'driving suite coverage is incomplete')
    need(driving.get('rom_unchanged_by_tests') and driving.get('test_sources_unchanged_during_run') and driving.get('test_sources_sha256')==current,'driving suite inputs changed')
    drive_names={'ntsc-track-'+str(t)+'-car-'+str(c) for t in range(3) for c in range(2)}|{'pal-track-2-car-0','pal-track-2-car-1'}
    negative_names={'negative-no-acceleration','negative-slow-racing'}
    need(len(driving.get('cases',[]))==10 and {c['name'] for c in driving['cases']}==drive_names|negative_names,'missing/duplicate driving cases')
    for case in driving['cases']:
        need(case.get('pass') is True,'driving case failed: '+case['name'])
        worker=read(case['report']);evidence.append(case['report'])
        need(worker.get('rom_sha256')==case['tested_rom_sha256'] and worker.get('core_sha256')==core_hash,'driving worker hash mismatch')
        if case['name'] in drive_names:
            need(worker.get('pass') is True and worker['rom_sha256']==rom_hash,'normal driving failed')
            marks={c['name']:c for c in worker.get('checks',[])}
            expected_marks={'01-selected-content','02-realtime-countdown','03-accelerator-moves-car','04-brakes-work','05-steering-turns-car','06-pause-and-live-renderer'}
            need(expected_marks<=marks.keys(),'missing physical-control proof')
            motion=marks['03-accelerator-moves-car']['details']
            need(motion['distance_m']>=6 and motion['speed_mps']>=4 and .90<=motion['game_clock_ratio']<=1.10,'motion/clock acceptance failed')
            need(motion['completed_game_fps']>=(10 if worker['video_standard']=='PAL' else 12),'native driving FPS floor failed')
            need(motion['distinct_live_scene_hashes']>=4 and motion['minimum_scene_colors']>=32,'no live 3D driving proof')
            if worker['track']==2 and worker['car']==0:
                need('07-course-finished-by-driving' in marks and marks['07-course-finished-by-driving']['telemetry']['checkpoint']==2 and marks['07-course-finished-by-driving']['telemetry']['state']==4,'Base course was not genuinely finished by racing')
        else:
            expected_errors=('ACCELERATOR_DID_NOT_MOVE_CAR',) if case['name']=='negative-no-acceleration' else ('SIMULATION_NOT_RUNNING_IN_REALTIME','COMPLETED_GAME_FPS_TOO_LOW','VISIBLE_GAME_FRAME_GAP_TOO_LONG')
            need(worker.get('pass') is False and case['worker_exit_code']!=0 and any(e in (worker.get('error') or '') for e in expected_errors),'driving negative did not reject for its intended reason')
    dsp_math=read('artifacts/dsp-math-report.json')
    need(dsp_math.get('pass') is True and dsp_math.get('core_sha256')==core_hash and dsp_math.get('released_game_unchanged') and dsp_math.get('arithmetic_operations',0)>=10240,'DSP arithmetic/render unit is stale or failed')
    need(all(v==0 for v in dsp_math.get('mismatches',{}).values()) and dsp_math.get('render_integer_mismatches')==0,'DSP unit mismatches')
    need(dsp_math.get('sources_sha256') and all(sha(R/name)==value for name,value in dsp_math['sources_sha256'].items()),'DSP arithmetic/render sources changed since unit run')
    evidence+=['artifacts/playability-regression/report.json','artifacts/dsp-math-report.json']
    evidence+=['artifacts/asset-report.json','artifacts/math-report.json','artifacts/build-reproducibility.json']
    return {'rom_sha256':rom_hash,'core_sha256':core_hash,'info':info,'suite':suite,'desktop':full_desktop,'desktop_report':desktop_path,'full_core':full_core,'assets':assets,'math':math,'build':build,'bios_causal':causal,'driving':driving,'dsp_math':dsp_math,'evidence':evidence}

if __name__=='__main__':
    try:
        d=verify();print(json.dumps({'pass':True,'rom_sha256':d['rom_sha256'],'normal_configurations':13,'specific_fault_controls':5,'both_full_core_paths':True,'full_desktop_gameplay':True,'stock_clock_driving_gate':True,'genuine_base_course_finish':True},indent=2))
    except (OSError,ValueError,KeyError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(1)
