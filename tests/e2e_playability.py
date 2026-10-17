#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Playability, not just boot: real input -> timed motion -> steering/braking.

The ACTUAL cartridge executes at stock Virtual Jaguar clocks. The host only
supplies controller buttons and reads native output/video. No state injection,
teleports, course-skipping, game simulation or substituted screenshots.
"""
from __future__ import annotations
from pathlib import Path
import argparse,datetime,hashlib,json,math,subprocess,sys,time,traceback
import numpy as np
from vj import VJ
R=Path(__file__).resolve().parents[1]
BUTTON={'a':8,'b':0,'left':6,'right':7,'down':5,'pause':2,'option':3,'restart':12}
class Failure(AssertionError):pass
class Driving:
    def __init__(self,a):
        self.a=a;self.out=a.output;self.out.mkdir(parents=True,exist_ok=True);self.started=time.monotonic();self.hz=50 if a.pal else 60
        self.v=VJ(a.core,a.rom,pal=a.pal,bios=a.bios=='on');self.checks=[];self.trace=[];self.active=False;self.previous_gpu=0;self.gpu_at=0;self.max_gap=0;self.stage='boot'
    def check(self,ok,message):
        if not ok:raise Failure(message+'; '+json.dumps(self.v.debug()))
    def step(self,n=1,buttons=None):
        if buttons is not None:self.v.buttons={BUTTON[x] for x in buttons}
        for _ in range(n):
            self.v.step();t=self.v.telemetry()
            if self.active:
                self.check(t['magic']==0x54524a31 and t['error']==0,'INVALID_NATIVE_RUNTIME')
                self.check(t['speed_q16']<150*65536,'PHYSICS_DIVERGED')
                if t['gpu_frames']!=self.previous_gpu:
                    self.max_gap=max(self.max_gap,self.v.frame-self.gpu_at);self.gpu_at=self.v.frame;self.previous_gpu=t['gpu_frames']
                self.check(self.v.frame-self.gpu_at<=self.hz,'NO_COMPLETED_GAME_FRAME_FOR_ONE_SECOND')
            if self.v.frame%10==0:self.trace.append({'frame':self.v.frame,'stage':self.stage,**t})
    def wait(self,predicate,seconds,buttons=None):
        if buttons is not None:self.v.buttons={BUTTON[x] for x in buttons}
        for _ in range(round(seconds*self.hz)):
            self.step()
            if predicate(self.v.telemetry()):return self.v.telemetry()
        raise Failure('TIMEOUT_'+self.stage.upper().replace(' ','_')+'; '+json.dumps(self.v.debug()))
    def mark(self,name,details=None):
        self.checks.append({'name':name,'frame':self.v.frame,'telemetry':self.v.telemetry(),'details':details or {}});self.v.save(self.out/(name+'.png'));print('PASS',name,details or '',flush=True)
    def tap(self,button,predicate):
        before=self.v.telemetry()['cpu_frames'];self.wait(lambda t:t['cpu_frames']>=before+2 and predicate(t),4,[button])
        before=self.v.telemetry()['cpu_frames'];self.wait(lambda t:t['cpu_frames']>=before+2,3,[])
    def forward(self):return math.atan2(self.v.i32(0x104c),self.v.i32(0x1048))
    @staticmethod
    def distance(a,b):return math.hypot(a['x_q16']-b['x_q16'],a['y_q16']-b['y_q16'])/65536
    def start(self):
        self.stage='countdown';begin=self.v.frame
        self.wait(lambda t:t['state']==1,2,['a'])
        self.wait(lambda t:t['state']==2,4.0,['a'])
        elapsed=(self.v.frame-begin)/self.hz
        self.check(2.8<=elapsed<=4.0,'COUNTDOWN_NOT_REALTIME')
        self.mark('02-realtime-countdown',{'emulated_seconds':elapsed})
    def run(self):
        self.wait(lambda t:t['magic']==0x54524a31 and t['state']==0 and t['gpu_frames']>=3,8,[])
        self.active=True;self.previous_gpu=self.v.telemetry()['gpu_frames'];self.gpu_at=self.v.frame
        while self.v.telemetry()['track']!=self.a.track:
            target=(self.v.telemetry()['track']+1)%3;self.tap('right',lambda t:t['track']==target)
        if self.v.telemetry()['car']!=self.a.car:self.tap('down',lambda t:t['car']==self.a.car)
        self.mark('01-selected-content');self.start()
        self.stage='acceleration';initial=self.v.telemetry();begin=self.v.frame;images=set();minimum_colors=100000
        self.max_gap=0;self.gpu_at=self.v.frame;self.previous_gpu=initial['gpu_frames']
        for _ in range(round(2.5*self.hz)):
            self.step(buttons=['a'])
            if self.v.frame%5==0:
                im=self.v.image;self.check(im is not None,'NO_VIDEO');roi=im[70:min(210,im.shape[0]-4),16:-16]
                images.add(hashlib.sha256(roi.tobytes()).hexdigest());minimum_colors=min(minimum_colors,len(np.unique(roi.reshape(-1,3),axis=0)))
        final=self.v.telemetry();seconds=(self.v.frame-begin)/self.hz;distance=self.distance(initial,final);speed=final['speed_q16']/65536
        ratio=(final['time_ms']-initial['time_ms'])/(1000*seconds);fps=(final['gpu_frames']-initial['gpu_frames'])/seconds
        self.check(.90<=ratio<=1.10,'SIMULATION_NOT_RUNNING_IN_REALTIME')
        self.check(fps>=(10 if self.a.pal else 12),'COMPLETED_GAME_FPS_TOO_LOW')
        self.check(self.max_gap<=round(self.hz*.30),'VISIBLE_GAME_FRAME_GAP_TOO_LONG')
        self.check(distance>=6 and speed>=4,'ACCELERATOR_DID_NOT_MOVE_CAR')
        self.check(len(images)>=4 and minimum_colors>=32,'NO_CHANGING_3D_DRIVING_VIDEO')
        self.check(final['checkpoint']>=1 and final['recorded_frames']>=8,'NO_REAL_CHECKPOINT_OR_REPLAY_PROGRESS')
        self.mark('03-accelerator-moves-car',{'emulated_seconds':seconds,'distance_m':distance,'speed_mps':speed,'completed_game_fps':fps,'game_clock_ratio':ratio,'distinct_live_scene_hashes':len(images),'minimum_scene_colors':minimum_colors})
        self.stage='braking';speed_before=speed;self.step(round(.7*self.hz),['b']);speed_after=self.v.telemetry()['speed_q16']/65536
        self.check(speed_after<speed_before*.9,'BRAKE_DOES_NOT_SLOW_CAR')
        self.mark('04-brakes-work',{'before_mps':speed_before,'after_mps':speed_after})
        self.stage='steering';angle=self.forward();before=self.v.telemetry();self.step(round(.9*self.hz),['a','left']);after=self.v.telemetry();change=(self.forward()-angle+math.pi)%(2*math.pi)-math.pi
        self.check(abs(change)>.05 and self.distance(before,after)>.5,'STEERING_DOES_NOT_TURN_MOVING_CAR')
        self.mark('05-steering-turns-car',{'heading_change_radians':change,'distance_m':self.distance(before,after)})
        self.stage='pause';self.tap('pause',lambda t:t['state']==3);paused=self.v.telemetry();self.step(self.hz,[]);still=self.v.telemetry()
        self.check(still['time_ms']==paused['time_ms'] and self.distance(still,paused)==0,'PAUSE_DID_NOT_STOP_PHYSICS')
        self.check(still['gpu_frames']>paused['gpu_frames'],'PAUSE_FROZE_RENDERER');self.mark('06-pause-and-live-renderer')
        if self.a.finish:
            self.tap('pause',lambda t:t['state']==2)
            self.stage='restart for genuine course completion';self.tap('restart',lambda t:t['state']==1)
            self.wait(lambda t:t['state']==2,4,['a']);begin=self.v.frame
            self.stage='ordered course finish';finished=self.wait(lambda t:t['state']==4,20,['a'])
            self.check(self.a.track==2 and finished['checkpoint']==2 and finished['time_ms']>1000,'NOT_A_GENUINE_RACING_COURSE_FINISH')
            self.mark('07-course-finished-by-driving',{'emulated_driving_seconds':(self.v.frame-begin)/self.hz,'finish_time_ms':finished['time_ms'],'ordered_checkpoints':2,'replay_button_never_used':True})
    def report(self,passed,error):
        result={'pass':passed,'test':'actual stock-clock Jaguar playability: throttle, real-time clock, visible frames, brake, steering, pause and optional ordered finish','date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rom_sha256':hashlib.sha256(self.a.rom.read_bytes()).hexdigest(),'core_sha256':hashlib.sha256(self.a.core.read_bytes()).hexdigest(),'track':self.a.track,'car':self.a.car,'video_standard':'PAL' if self.a.pal else 'NTSC','bios':self.a.bios,'emulator_frames':self.v.frame,'wall_seconds':time.monotonic()-self.started,'maximum_observed_gpu_frame_gap_vbl':self.max_gap,'checks':self.checks,'error':error,'limitations':['Finite stock-emulator scenarios, not a guarantee for all tracks/driving paths or hardware.','Full original editor, persistence, account/network and fidelity parity remain separate incomplete requirements.']}
        (self.out/'report.json').write_text(json.dumps(result,indent=2)+'\n');(self.out/'telemetry.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.trace));return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rom',type=Path,default=R/'releases/trigger-rally-jaguar.j64');p.add_argument('--core',type=Path,default=R/'vendor/bin/virtualjaguar_libretro.so');p.add_argument('--output',type=Path,default=R/'artifacts/playability/driving');p.add_argument('--track',type=int,choices=range(3),default=0);p.add_argument('--car',type=int,choices=range(2),default=0);p.add_argument('--bios',choices=['on','off'],default='off');p.add_argument('--pal',action='store_true');p.add_argument('--finish',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--timeout',type=int,default=180);a=p.parse_args()
    if not a.worker:
        cmd=[sys.executable,__file__,*sys.argv[1:],'--worker']
        try:return subprocess.run(cmd,cwd=R,timeout=a.timeout).returncode
        except subprocess.TimeoutExpired:print('FAIL external playability timeout',flush=True);return 124
    run=None;passed=False;error=None
    try:run=Driving(a);run.run();passed=True
    except Exception as exc:error=type(exc).__name__+': '+str(exc);traceback.print_exc()
    finally:
        if run:run.report(passed,error);run.v.close()
    return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
