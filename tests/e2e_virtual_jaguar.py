#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""End-to-end regression test of the ACTUAL Trigger Rally Jaguar cartridge.

Uses the real Virtual Jaguar libretro emulator, stock clocks, BIOS, GPU, DSP,
object processor, blitter, framebuffer, audio and controller matrix. This is
NOT a port simulation or an engine-demo test. No writes to emulated RAM, CPU
registers or emulator clocks are made. The only interaction is controller input.

A deliberately broken CARTRIDGE (not a memory patch) is a negative control.
See docs/TESTING.md for the exact coverage, limitations, and watchdog budgets.
"""
from __future__ import annotations
import argparse,datetime,hashlib,json,math,os,subprocess,sys,time,traceback
from pathlib import Path
import numpy as np
from vj import VJ
R=Path(__file__).resolve().parents[1]
DEFAULT_CORE=R/'vendor/bin/virtualjaguar_libretro.so'
if not DEFAULT_CORE.exists():DEFAULT_CORE=R.parent/'tools/virtualjaguar-libretro/virtualjaguar_libretro.so'
BUTTONS={'a':8,'b':0,'c':1,'pause':2,'option':3,'up':4,'down':5,'left':6,'right':7,'0':9,'1':10,'2':11,'3':12}
STATES=['menu','countdown','racing','paused','finished','replay']
class CheckFailure(AssertionError):pass
class Run:
    def __init__(self,args):
        self.args=args;self.out=args.output;self.out.mkdir(parents=True,exist_ok=True)
        self.started=time.monotonic();self.v=VJ(args.core,args.rom,args.pal,bios=args.bios=="on",fastblitter=args.blitter=="fast")
        self.checks=[];self.trace=[];self.stage='boot';self.last_cpu=self.last_gpu=0;self.cpu_at=self.gpu_at=0
        self.max_cpu_gap=self.max_gpu_gap=0;self.black_streak=self.max_black_streak=0;self.active=False;self.last_visual={};self.visual_hashes=set();self.race_hashes=set();self.frame_observations=0
        self.gpu_changes=[];self.cpu_changes=[];self.min_nonblack=1.;self.min_colors=1000000
    def check(self,condition,message):
        if not condition:raise CheckFailure(message+'; '+json.dumps(self.v.debug()))
    def mark(self,name,details=None):
        row={'name':name,'emulator_frame':self.v.frame,'telemetry':self.v.telemetry(),'details':details or {}}
        self.checks.append(row);self.v.save(self.out/(name+'.png'))
        print(f"PASS {name}: frame={self.v.frame} cpu={row['telemetry']['cpu_frames']} gpu={row['telemetry']['gpu_frames']} state={STATES[row['telemetry']['state']]}",flush=True)
    def inspect(self):
        v=self.v;t=v.telemetry();self.trace.append({'frame':v.frame,'stage':self.stage,**t,'cpu_pc':hex(v.lib.m68k_get_reg(None,16)),'gpu_pc':hex(v.lib.GPUGetPC())})
        if not self.active:return
        self.check(t['magic']==0x54524a31,'Native telemetry signature disappeared')
        self.check(t['error']==0,'Native runtime reported an error')
        self.check(t['state']<len(STATES),'Invalid game state')
        # Q16.16 world coordinates/speeds must stay within sane world bounds.
        self.check(abs(t['x_q16'])<16000*65536 and abs(t['y_q16'])<16000*65536,'Vehicle coordinates escaped the world')
        self.check(-200*65536<t['z_q16']<4000*65536,'Vehicle altitude invalid')
        self.check(t['speed_q16']<500*65536,'Vehicle physics diverged')
        if t['cpu_frames']!=self.last_cpu:
            self.max_cpu_gap=max(self.max_cpu_gap,v.frame-self.cpu_at);self.cpu_at=v.frame;self.last_cpu=t['cpu_frames'];self.cpu_changes.append(v.frame)
        if t['gpu_frames']!=self.last_gpu:
            self.max_gpu_gap=max(self.max_gpu_gap,v.frame-self.gpu_at);self.gpu_at=v.frame;self.last_gpu=t['gpu_frames'];self.gpu_changes.append(v.frame)
        # Conservative 15-second game-frame watchdog. This is NOT a claim of
        # acceptable real-time performance: measured gaps/FPS are reported.
        budget=(50 if self.args.pal else 60)*15
        self.check(v.frame-self.cpu_at<=budget,'Native game loop stopped making progress')
        self.check(v.frame-self.gpu_at<=budget,'GPU stopped completing submitted frames')
        self.check(v.image is not None,'Emulator produced no framebuffer')
        im=v.image;roi=im[70:min(210,im.shape[0]-4),16:im.shape[1]-16]
        self.check(roi.size>0,'Invalid framebuffer geometry')
        nonblack=float(np.mean(np.max(roi,axis=2)>8));colors=int(len(np.unique(roi.reshape(-1,3),axis=0)))
        digest=hashlib.sha256(roi.tobytes()).hexdigest()
        self.last_visual={'nonblack_fraction':nonblack,'unique_colors':colors,'scene_sha256':digest,'width':im.shape[1],'height':im.shape[0]}
        self.visual_hashes.add(digest);self.frame_observations+=1
        if t['state']==2:self.race_hashes.add(digest)
        self.min_nonblack=min(self.min_nonblack,nonblack);self.min_colors=min(self.min_colors,colors)
        self.black_streak=self.black_streak+10 if nonblack<.02 or colors<8 else 0
        self.max_black_streak=max(self.max_black_streak,self.black_streak)
        self.check(self.black_streak<=(50 if self.args.pal else 60)*2,'Framebuffer froze into a black/empty screen')
    def step(self,n=1):
        for _ in range(n):
            self.v.step()
            if self.v.frame%10==0:self.inspect()
    def wait(self,predicate,budget=2400,buttons=None,min_frames=0):
        if buttons is not None:self.v.buttons={BUTTONS[b] for b in buttons}
        start=self.v.frame;base=self.v.telemetry()['cpu_frames']
        while self.v.frame-start<budget:
            self.step()
            t=self.v.telemetry()
            if t['cpu_frames']>=base+min_frames and predicate(t):return t
        raise CheckFailure('Timed out waiting in '+self.stage+'; '+json.dumps(self.v.debug()))
    def release(self):return self.wait(lambda t:True,2400,[],1)
    def press(self,button,predicate=lambda t:True,budget=2400):
        t=self.wait(predicate,budget,[button],1);self.release();return t
    def game_frames(self,n,buttons=None,budget=12000):return self.wait(lambda t:True,budget,buttons,n)
    def boot(self,name="01-cold-boot"):
        self.wait(lambda t:t['magic']==0x54524a31 and t['gpu_frames']>=2 and t['cpu_frames']>=2,600,[])
        self.active=True;self.cpu_at=self.gpu_at=self.v.frame;self.last_cpu=self.v.telemetry()['cpu_frames'];self.last_gpu=self.v.telemetry()['gpu_frames'];self.inspect()
        self.check(self.v.telemetry()['state']==0,'Cartridge did not cold-boot to its menu')
        self.check(self.last_visual['nonblack_fraction']>.15 and self.last_visual['unique_colors']>=32,'Menu has no real rendered 3D scene')
        self.mark(name,self.last_visual)
    def run(self):
        self.boot()
        if self.args.mode=='boot':
            self.step(300);self.mark('02-boot-soak');self.reset_check();return
        self.stage='menu controls and all shipped content'
        for track in range(3):
            for car in range(2):
                t=self.v.telemetry()
                if t['track']!=track:self.press('right',lambda t:t['track']==track)
                if self.v.telemetry()['car']!=car:self.press('down',lambda t:t['car']==car)
                self.game_frames(2,[])
                self.check(self.v.telemetry()['track']==track and self.v.telemetry()['car']==car,'Track/car selection failed')
                self.mark(f'02-track-{track}-car-{car}',self.last_visual)
        # Return to original car/track through genuine controller input.
        self.press('right',lambda t:t['track']==0)
        self.press('down',lambda t:t['car']==0)
        self.stage='idle soak';base=self.v.telemetry();self.step(600)
        self.check(self.v.telemetry()['gpu_frames']>=base['gpu_frames']+5,'Menu renderer stopped during idle soak')
        self.mark('03-idle-soak')
        self.stage='countdown and racing'
        self.press('a',lambda t:t['state']==1)
        self.mark('04-countdown')
        self.wait(lambda t:t['state']==2,16000,['a'])
        start=self.v.telemetry();self.mark('05-racing-start')
        self.wait(lambda t:t['time_ms']>=1800,18000,['a'])
        moving=self.v.telemetry();distance=math.hypot(moving['x_q16']-start['x_q16'],moving['y_q16']-start['y_q16'])/65536
        self.check(distance>2 and moving['speed_q16']>65536,'Throttle did not produce real vehicle motion')
        self.check(moving['recorded_frames']>=8,'Native replay recording did not collect frames')
        self.check(moving['checkpoint']>=1,'Ordered checkpoint detection never advanced')
        self.check(len(self.race_hashes)>=3,'Rendered racing scene did not change as the car moved')
        self.mark('06-throttle-physics',{'distance_m':distance,'distinct_scene_hashes':len(self.race_hashes)})
        self.stage='pause and resume'
        self.press('pause',lambda t:t['state']==3)
        paused=self.v.telemetry();self.game_frames(4,[]);after=self.v.telemetry()
        self.check(after['time_ms']==paused['time_ms'],'Race clock advanced while paused')
        self.check((after['x_q16'],after['y_q16'],after['z_q16'])==(paused['x_q16'],paused['y_q16'],paused['z_q16']),'Vehicle moved while paused')
        self.check(after['gpu_frames']>paused['gpu_frames'],'Pause froze the renderer')
        self.mark('07-pause-keeps-rendering')
        self.press('pause',lambda t:t['state']==2)
        self.stage='steering, camera and brake'
        self.game_frames(2,['a','left']);self.check(self.v.telemetry()['input']&(1<<22),'Left steering did not reach Jaguar controller scan')
        self.release();self.press('2');self.game_frames(2,['b']);self.check(self.v.telemetry()['input']&(1<<25),'Brake input did not reach native runtime')
        self.mark('08-steer-camera-brake')
        self.stage='native replay'
        self.press('option',lambda t:t['state']==0)
        self.check(self.v.telemetry()['recorded_frames']>=8,'Recording disappeared on return to menu')
        self.press('1',lambda t:t['state']==5)
        self.mark('09-replay')
        self.wait(lambda t:t['state']==4,6000,[])
        self.mark('10-replay-completed')
        self.stage='restart'
        self.press('3',lambda t:t['state']==1)
        self.check(self.v.telemetry()['time_ms']==0 and self.v.telemetry()['recorded_frames']==0,'Restart failed to reset race/replay state')
        self.mark('11-restart')
        self.press('option',lambda t:t['state']==0)
        self.stage='alternate tracks under simulation'
        for track,car in ((1,1),(2,0)):
            self.press('right',lambda t:t['track']==track)
            if self.v.telemetry()['car']!=car:self.press('down',lambda t:t['car']==car)
            self.press('a',lambda t:t['state']==1)
            self.game_frames(3,['a'],10000)
            self.mark(f'12-live-track-{track}-car-{car}')
            self.press('option',lambda t:t['state']==0)
        self.stage='final soak';self.step(600);self.mark('13-final-soak')
        self.check(self.v.audio_nonzero>1000 and self.v.audio_peak>50,'DSP produced no audible PCM samples')
        self.reset_check()
    def reset_check(self):
        self.stage='console reset';self.active=False;self.v.buttons=set();self.v.reset()
        self.boot('14-console-reset');self.step(300);self.mark('15-reset-soak')
    def report(self,passed,error=None):
        fps=50 if self.args.pal else 60
        runtime_frames=max(1,self.v.frame-self.checks[0]['emulator_frame']) if self.checks else 1
        runtime_seconds=runtime_frames/fps
        measured=len(self.gpu_changes)/runtime_seconds
        result={'pass':passed,'test':'actual Trigger Rally Jaguar ROM in real Virtual Jaguar','mode':self.args.mode,'video_standard':'PAL' if self.args.pal else 'NTSC','bios':self.args.bios,'blitter':self.args.blitter,'isolated_saved_state':True,'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rom':str(self.args.rom.resolve()),'rom_sha256':hashlib.sha256(self.args.rom.read_bytes()).hexdigest(),'core_sha256':hashlib.sha256(self.args.core.read_bytes()).hexdigest(),'core_source_commit':'6bf3574c1a98ccd57719ff6b822122017b8e5942','emulator_frames':self.v.frame,'wall_seconds':time.monotonic()-self.started,'checks':self.checks,'last_state':self.v.debug(),'video':{'samples_checked':self.frame_observations,'distinct_scene_hashes':len(self.visual_hashes),'racing_scene_hashes':len(self.race_hashes),'minimum_nonblack_fraction':self.min_nonblack,'minimum_scene_colors':self.min_colors,'longest_black_streak_frames':self.max_black_streak,'max_cpu_frame_gap_vbl':self.max_cpu_gap,'max_gpu_frame_gap_vbl':self.max_gpu_gap,'mean_completed_game_frames_per_emulated_second':measured,'performance_warning':'Mixed-state FPS below 15; this watchdog test is not a playability approval. Consult the separate stock-clock driving suite.' if measured<15 else None},'audio':{'stereo_sample_frames':self.v.audio_samples,'nonzero_samples':self.v.audio_nonzero,'peak':self.v.audio_peak},'watchdogs':{'boot_vbl':600,'cpu_gpu_progress_seconds':15,'black_screen_seconds':2},'limitations':['Finite regression run, not a proof of never freezing.','Does not establish feature parity, acceptable performance, track completion, persistent storage, editor, sharing, hardware compatibility, or cycle accuracy.','PAL boot smoke test is separate from the full NTSC interaction test.'],'error':error}
        (self.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');(self.out/'telemetry.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in self.trace))
        if self.v.image is not None:self.v.save(self.out/('last-frame.png' if passed else 'FAILURE.png'))
        return result

def worker(a):
    run=None;error=None;passed=False
    try:run=Run(a);run.run();passed=True
    except Exception as e:error=type(e).__name__+': '+str(e);traceback.print_exc()
    finally:
        if run:
            report=run.report(passed,error);run.v.close()
            print(('PASS' if passed else 'FAIL')+' actual-ROM Virtual Jaguar test; report '+str(a.output/'report.json'),flush=True)
        else:
            a.output.mkdir(parents=True,exist_ok=True);(a.output/'report.json').write_text(json.dumps({'pass':False,'error':error},indent=2))
    return 0 if passed else 1

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--core',type=Path,default=DEFAULT_CORE);p.add_argument('--rom',type=Path,default=R/'releases/trigger-rally-jaguar.j64');p.add_argument('--output',type=Path,default=R/'artifacts/e2e-ntsc');p.add_argument('--pal',action='store_true');p.add_argument('--bios',choices=['on','off'],default='on');p.add_argument('--blitter',choices=['accurate','fast'],default='accurate');p.add_argument('--mode',choices=['full','boot'],default='full');p.add_argument('--timeout',type=int,default=900);p.add_argument('--negative-control',action='store_true');p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
    if a.worker:return worker(a)
    if not a.core.exists():p.error('Build or supply a TEST_EXPORTS=1 Virtual Jaguar libretro core. See docs/TESTING.md.')
    if a.negative_control:
        a.output=a.output if a.output!=R/'artifacts/e2e-ntsc' else R/'artifacts/e2e-negative-control';a.output.mkdir(parents=True,exist_ok=True)
        broken=bytearray(a.rom.read_bytes());broken[0x410:0x412]=b'\x60\xfe' # native CPU infinite branch at actual entry
        a.rom=a.output/'deliberately-broken.j64';a.rom.write_bytes(broken);a.mode='boot'
    cmd=[sys.executable,str(Path(__file__).resolve()),'--worker','--core',str(a.core.resolve()),'--rom',str(a.rom.resolve()),'--output',str(a.output.resolve()),'--mode',a.mode,'--bios',a.bios,'--blitter',a.blitter]+(['--pal'] if a.pal else [])
    try:rc=subprocess.run(cmd,timeout=a.timeout).returncode
    except subprocess.TimeoutExpired:
        a.output.mkdir(parents=True,exist_ok=True);(a.output/'report.json').write_text(json.dumps({'pass':False,'error':'External wall-clock watchdog killed emulator worker after '+str(a.timeout)+' seconds.'},indent=2)+'\n');rc=124
    if a.negative_control:
        report=json.loads((a.output/'report.json').read_text());detected=rc!=0 and not report['pass'] and ('Timed out' in report.get('error','') or 'framebuffer' in report.get('error','').lower())
        summary={'pass':detected,'intentionally_broken_rom_detected':detected,'worker_exit_code':rc,'failure_report':'report.json','method':'Replaced the actual cartridge entry instruction by a 68000 BRA.S to itself; no emulator-state patching.'}
        (a.output/'negative-control.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2));return 0 if detected else 1
    return rc
if __name__=='__main__':raise SystemExit(main())
