#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Black-screen E2E of the actual cartridge in the desktop Virtual Jaguar.

Runs a real X11 application on an isolated Xvfb display, with fresh HOME/XDG
settings, no saved states, real keyboard/controller events and actual window
captures. Reads the game's existing bitmap font and its visible GPU-frame
counter; no process-memory access, emulator patches, host physics or mock video.

A parent watchdog kills the entire worker/emulator/display process group if
any child blocks. Missing dependencies FAIL, rather than silently skipping.
"""
from __future__ import annotations
import argparse, hashlib, io, json, os, re, select, shutil, signal, struct
import subprocess, sys, tempfile, time, traceback
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

R = Path(__file__).resolve().parents[1]

class Failure(AssertionError):
    pass

class NativeHUD:
    """Exact matching against the ROM's real 8x8 font, not OCR heuristics."""
    def __init__(self):
        font = (R/'src/font8x8.bin').read_bytes()
        self.glyphs = {chr(c): np.unpackbits(np.frombuffer(font[8+c*8:16+c*8], dtype=np.uint8)).reshape(8,8)*255 for c in range(32,127)}
        self.title = np.hstack([self.glyphs[c] for c in 'TRIGGER RALLY / ATARI'])
        self.canonical={c:min(k for k,g in self.glyphs.items() if np.array_equal(g,v)) for c,v in self.glyphs.items()}
        self.layout = None
        self.templates = {}

    def locate(self, image):
        mask = (image.min(axis=2)>190).astype(np.uint8)*255
        if self.layout:
            x,y,sx,sy = self.layout
            for alg in (cv2.INTER_NEAREST,cv2.INTER_NEAREST_EXACT):
                target=cv2.resize(self.title,(round(self.title.shape[1]*sx),round(8*sy)),interpolation=alg)
                patch=mask[y:y+target.shape[0],x:x+target.shape[1]]
                if patch.shape==target.shape and np.mean(patch==target)>.97:
                    return self.layout
        # Desktop 2.1.x displays the native 384-wide scene with non-square pixels.
        # Also accept 1x/2x square-pixel outputs used by other packaged builds.
        best = None
        for sx,sy in [(1.5,2),(.75,1),(1,1),(2,2),(1.5,1.5),(1,2),(2,1)]:
            # PAL and NTSC use opposite OpenGL tie phases at the left edge.
            # Require the same exact glyph match, in either known rasterization.
            for alg in (cv2.INTER_NEAREST,cv2.INTER_NEAREST_EXACT):
                needle=cv2.resize(self.title,(round(self.title.shape[1]*sx),round(8*sy)),interpolation=alg)
                if needle.shape[0]>mask.shape[0] or needle.shape[1]>mask.shape[1]:continue
                scores=cv2.matchTemplate(mask,needle,cv2.TM_CCOEFF_NORMED)
                _,score,_,pos=cv2.minMaxLoc(scores)
                if best is None or score>best[0]:best=(score,pos,sx,sy)
        if best and best[0]>.97:
            _,(x,y),sx,sy=best
            self.layout=(x,y,sx,sy)
            # OpenGL's sample origin can change by one destination pixel
            # across a non-square-pixel viewport, and PAL uses the opposite
            # left-edge tie phase. These are exact nearest/glyph translations,
            # not a looser similarity threshold or inferred frame numbers.
            self.templates={}
            for c,g in self.glyphs.items():
                variants=[]
                for alg in (cv2.INTER_NEAREST,cv2.INTER_NEAREST_EXACT):
                    t=cv2.resize(g,(round(8*sx),round(8*sy)),interpolation=alg)
                    for dx in [-1,0,1]:
                        shifted=np.roll(t,dx,axis=1)
                        if dx<0:shifted[:,dx:]=0
                        if dx>0:shifted[:,:dx]=0
                        variants.append(shifted)
                self.templates[c]=variants
            self.template_keys=list(self.templates)
            self.template_stack=np.asarray(list(self.templates.values()))
            return self.layout
        return None

    def fold(self,text):
        return ''.join(self.canonical.get(c,c) for c in text).upper()

    def text(self, image, row, col=0, length=48):
        if not self.layout:
            return None
        x,y,sx,sy=self.layout
        result=''
        for i in range(length):
            px=x+round((col+i)*8*sx);py=y+round(row*8*sy)
            w,h=round(8*sx),round(8*sy)
            patch=image[py:py+h,px:px+w]
            if patch.shape[:2]!=(h,w):
                return None
            patch=(patch.min(axis=2)>190).astype(np.uint8)*255
            # GL nearest-neighbour tie rounding changes phase across the window.
            # Each variant is an exact nearest/pixel-phase rasterization.
            errors=(patch!=self.template_stack).mean(axis=(2,3)).min(axis=1)
            best=int(errors.argmin());err=float(errors[best]);char=self.template_keys[best]
            result += char if err<.06 else '?'
        return result

    def decode(self,image):
        if not self.locate(image):
            return None
        rows=[self.text(image,r) for r in range(5)]
        if any(row is None for row in rows):
            return None
        counter=rows[0][38:44]
        return {'rows':rows,'gpu_frame':int(counter) if counter.isdigit() else None}

class DesktopRun:
    def __init__(self,args):
        self.a=args;self.out=args.output.resolve();self.out.mkdir(parents=True,exist_ok=True)
        for old in self.out.iterdir():
            if old.is_file() and (old.name in {'report.json','screens.jsonl','FAILURE.png','last-frame.png'} or re.fullmatch(r'\d\d-[a-zA-Z0-9-]+\.png',old.name)):
                old.unlink()
        self.started=time.monotonic();self.last=None;self.last_image=None;self.checks=[];self.trace=[]
        self.hud=NativeHUD();self.children=[];self.active=False;self.black_since=None;self.gpu_at=None
        self.previous_gpu=None;self.max_gpu_gap=0.;self.black_observations=0;self.samples=0
        self.max_nonblack=0.;self.scene_hashes=set();self.last_scene=None;self.win=None
        self.tmp=tempfile.TemporaryDirectory(prefix='virtualjaguar-desktop-')
        self.home=Path(self.tmp.name)
        self.env=dict(os.environ)
        # Some OpenCV wheels export their private, incompatible Qt plugin path.
        # The tested program must use its OWN system Qt, not cv2's Qt plugins.
        for name in ['QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_FONTDIR','QT_PLUGIN_PATH']:
            self.env.pop(name,None)
        self.env['QT_QPA_PLATFORM']='xcb'
        for name in ['home','config','data','runtime']:
            (self.home/name).mkdir(mode=0o700)
        self.env.update(HOME=str(self.home/'home'),XDG_CONFIG_HOME=str(self.home/'config'),XDG_DATA_HOME=str(self.home/'data'),XDG_RUNTIME_DIR=str(self.home/'runtime'),SDL_AUDIODRIVER='dummy',LIBGL_ALWAYS_SOFTWARE='1',MESA_SHADER_CACHE_DISABLE='true',QT_X11_NO_MITSHM='1',QT_STYLE_OVERRIDE='Fusion')
        self.emulog=open(self.out/'emulator.log','wb');self.xlog=open(self.out/'xvfb.log','wb')

    def check(self,condition,message):
        if not condition:
            raise Failure(message)

    def launch(self):
        cfg=self.home/'config/Underground Software/Virtual Jaguar.conf';cfg.parent.mkdir(parents=True)
        # Only UI placement/known standard controller bindings are preseeded.
        # The default BIOS case deliberately leaves useJaguarBIOS unspecified.
        general='[General]\nGPUEnabled=true\nDSPEnabled=true\nuseFastBlitter=false\nuseOpenGL=true\nglFilterType=0\nzoom=2\nfullscreen=false\npos=@Point(5 5)\nshowUnknownSoftware=true\n'
        maps=[83,88,90,67,45,55,52,49,48,56,53,50,61,57,54,51,76,75,74,79,80]
        cfg.write_text(general+'\n[profiles]\nsize=1\n1\\deviceNum=0\n1\\mapName=Default\n1\\preferredSlot=1\n'+''.join(f'1\\map{i}={v}\n' for i,v in enumerate(maps)))
        rd,wr=os.pipe()
        x=subprocess.Popen(['Xvfb','-displayfd',str(wr),'-screen','0','1024x768x24','-nolisten','tcp'],pass_fds=(wr,),stdout=self.xlog,stderr=self.xlog)
        self.children.append(x);os.close(wr)
        try:
            self.check(bool(select.select([rd],[],[],15)[0]),'Xvfb did not start in 15 seconds')
            display=os.read(rd,64).decode().strip()
        finally:
            os.close(rd)
        self.check(display.isdigit(),'Xvfb returned an invalid display number')
        self.env['DISPLAY']=':'+display
        # A held physical Jaguar button has no X11 key-repeat release edges.
        # Disable repeat only on this isolated test display, not in the emulator.
        subprocess.run(['xset','r','off'],env=self.env,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
        command=[str(self.a.emulator.resolve()),str(self.a.rom.resolve()),'--'+self.a.standard,'--gpu','--dsp','--no-blur','--no-log']
        if self.a.bios!='default':
            command.append('--bios' if self.a.bios=='on' else '--no-bios')
        self.command=command
        self.gui=subprocess.Popen(command,env=self.env,cwd=self.home,stdout=self.emulog,stderr=self.emulog)
        self.children.append(self.gui)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            self.check(self.gui.poll() is None,'Desktop Virtual Jaguar exited before opening its window')
            q=self.xdo('search','--onlyvisible','--pid',str(self.gui.pid),'--name','^Virtual Jaguar v',check=False)
            if q.returncode==0 and q.stdout.strip():
                self.win=q.stdout.decode().splitlines()[0];break
            time.sleep(.1)
        self.check(self.win is not None,'No actual desktop Virtual Jaguar window appeared')
        self.xdo('windowfocus','--sync',self.win)

    def xdo(self,*args,check=True):
        return subprocess.run(['xdotool',*map(str,args)],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=check,timeout=5)

    def capture(self):
        self.check(self.gui.poll() is None,'Desktop emulator exited during the test')
        p=subprocess.run(['import','-window',self.win,'png:-'],env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8)
        self.check(p.returncode==0,'Failed to capture actual emulator window: '+p.stderr.decode(errors='replace'))
        self.last_image=np.asarray(Image.open(io.BytesIO(p.stdout)).convert('RGB'))
        decoded=self.hud.decode(self.last_image)
        now=time.monotonic();self.samples+=1
        if self.hud.layout:
            x,y,sx,sy=self.hud.layout
            # Exclude HUD, emulator menus, status bar/FPS and screen margins.
            roi=self.last_image[y+round(44*sy):min(y+round(202*sy),self.last_image.shape[0]-34),x+round(8*sx):min(x+round(376*sx),self.last_image.shape[1]-18)]
        else:
            roi=self.last_image[110:-45,30:-30]
        self.check(roi.size>0,'Invalid desktop framebuffer/crop geometry')
        nonblack=float((roi.max(axis=2)>12).mean())
        colors=int(len(np.unique(roi.reshape(-1,3),axis=0)))
        horizontal_variation=float(roi.astype(np.float32).std(axis=1).mean())
        scene={'nonblack_fraction':nonblack,'colors':colors,'horizontal_variation':horizontal_variation,'sha256':hashlib.sha256(roi.tobytes()).hexdigest()}
        self.max_nonblack=max(self.max_nonblack,nonblack)
        black=nonblack<.02 or colors<8
        if black:
            self.black_observations+=1
            if self.black_since is None:self.black_since=now
        else:
            self.black_since=None
        if decoded:
            decoded['scene']=scene
        if decoded and decoded['gpu_frame'] is not None:
            self.last=decoded
            self.scene_hashes.add(scene['sha256']);self.last_scene=roi.copy()
            g=decoded['gpu_frame']
            if g is not None and g!=self.previous_gpu:
                if self.gpu_at is not None:self.max_gpu_gap=max(self.max_gpu_gap,now-self.gpu_at)
                self.previous_gpu=g;self.gpu_at=now
        self.trace.append({'wall_seconds':now-self.started,'native_hud':decoded,'scene':scene})
        if self.active:
            self.check(self.black_since is None or now-self.black_since<2,'BLACK_SCREEN: game scene stayed black/empty for two seconds')
            self.check(self.gpu_at is not None and now-self.gpu_at<20,'FROZEN_GAME: visible native GPU-frame counter stopped advancing for 20 seconds (emulator FPS is not game progress)')
        return decoded

    def wait(self,predicate,budget=30):
        start=time.monotonic()
        while time.monotonic()-start<budget:
            d=self.capture()
            if d is not None and d['gpu_frame'] is not None and predicate(d):
                return d
            time.sleep(.2)
        black=bool(self.trace) and self.trace[-1]['scene']['nonblack_fraction']<.02
        raise Failure(('BLACK_BOOT' if black else 'NATIVE_GAME_TIMEOUT')+': no required visible game state within '+str(budget)+' seconds; last='+str(self.last))

    def mark(self,name):
        self.checks.append({'name':name,'wall_seconds':time.monotonic()-self.started,'native_hud':self.last})
        Image.fromarray(self.last_image).save(self.out/(name+'.png'))
        print('PASS desktop '+name+' GPU='+str(self.last['gpu_frame']),flush=True)

    def boot(self,name='01-cold-boot'):
        self.active=False;self.previous_gpu=None;self.gpu_at=None;self.black_since=None
        d=self.wait(lambda d:d['gpu_frame']>=2 and (not hasattr(self,'reset_limit') or d['gpu_frame']<self.reset_limit) and d['rows'][1].upper().startswith(self.hud.fold('TRACK:')) and d['scene']['nonblack_fraction']>.15 and d['scene']['colors']>=32 and d['scene']['horizontal_variation']>3,45)
        self.active=True;self.mark(name)
        self.soak(3,2)

    def soak(self,seconds,min_gpu=1):
        start=time.monotonic();g=self.last['gpu_frame']
        while time.monotonic()-start<seconds:
            self.capture();time.sleep(.2)
        self.check(self.last['gpu_frame']>=g+min_gpu,'Native GPU failed to complete enough frames during idle/pause soak')

    def press(self,key,predicate):
        before=self.last['gpu_frame']
        self.xdo('keydown',key)
        try:
            d=self.wait(lambda d:d['gpu_frame']>before and predicate(d),40)
        finally:
            self.xdo('keyup',key)
        accepted=d['gpu_frame']
        # Wait for a native input scan with the button released as well.
        self.wait(lambda d:d['gpu_frame']>accepted and predicate(d),40)

    @staticmethod
    def clock(d):
        s=d['rows'][1][28:36]
        if re.fullmatch(r'\d\d:\d\d\.\d\d',s):
            return int(s[:2])*60+int(s[3:5])+int(s[6:])/100
        return None

    def run(self):
        self.launch();self.boot();self.mark('02-idle-live-renderer')
        if self.a.mode=='watchdog':
            # Same capture/watchdog implementation, with an observable healthy
            # interval before a post-boot fault. Do not let a short idle-soak
            # assertion mask the specific 20-second frozen-frame watchdog.
            self.soak(35,1);self.mark('03-watchdog-healthy-soak');return
        bank=(R/'assets/assets.bin').read_bytes();h=struct.unpack_from('>13I',bank)
        names=lambda p,n,stride,width:[bank[p-0x840000+i*stride:p-0x840000+i*stride+width].split(b'\0')[0].decode() for i in range(n)]
        tracks=names(h[8]+16,h[2],108,32);cars=names(h[9],h[3],612,32)
        # Native keyboard mapping confirmed from Virtual Jaguar controller settings.
        track=car=0
        for ti in range(3):
            for ci in range(2):
                old_hash=self.last['scene']['sha256']
                if ti!=track:
                    self.press('c',lambda d:self.hud.fold(tracks[ti]) in d['rows'][1].upper());track=ti
                    self.check(self.last['scene']['sha256']!=old_hash,'Track label changed but rendered 3D scene did not')
                if ci!=car:
                    self.press('s',lambda d:self.hud.fold(cars[ci]) in d['rows'][2].upper());car=ci
                self.mark(f'03-track-{ti}-car-{ci}')
        self.press('c',lambda d:self.hud.fold(tracks[0]) in d['rows'][1].upper())
        self.press('s',lambda d:self.hud.fold(cars[0]) in d['rows'][2].upper())
        if self.a.mode=='full':
            self.press('l',lambda d:d['rows'][1].upper().startswith(self.hud.fold('READY')));self.mark('04-countdown')
            self.xdo('keydown','l')
            try:
                self.wait(lambda d:d['rows'][1].upper().startswith(self.hud.fold('RACING')),330)
                first_scene=self.last['scene']['sha256'];self.mark('05-racing')
                self.wait(lambda d:self.clock(d) is not None and self.clock(d)>=1.5 and d['rows'][2][5:8].isdigit() and int(d['rows'][2][5:8])>=2,330)
                self.check(self.last['scene']['sha256']!=first_scene,'Race clock advanced but scene remained frozen')
                self.mark('06-throttle-scene-motion')
            finally:
                self.xdo('keyup','l')
            self.press('p',lambda d:d['rows'][1].upper().startswith(self.hud.fold('PAUSED')))
            self.wait(lambda d:self.clock(d) is not None,10)
            before=self.clock(self.last);self.soak(3,2)
            self.wait(lambda d:self.clock(d) is not None,10)
            self.check(self.clock(self.last)==before,'Race clock changed while paused')
            self.mark('07-paused-live-renderer')
            self.press('p',lambda d:d['rows'][1].upper().startswith(self.hud.fold('RACING')))
            self.press('o',lambda d:d['rows'][1].upper().startswith(self.hud.fold('TRACK:')));self.mark('08-return-to-menu')
        self.active=False;self.reset_limit=self.last['gpu_frame']
        self.xdo('mousemove','--window',self.win,'28','39','click','1')
        time.sleep(.4)
        self.xdo('mousemove','--window',self.win,'28','39','click','1')
        self.boot('09-desktop-power-cycle');self.mark('10-final-live-soak')

    def close(self):
        for p in reversed(self.children):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=2)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
        self.emulog.close();self.xlog.close();self.tmp.cleanup()

    def report(self,passed,error):
        if self.last_image is not None:Image.fromarray(self.last_image).save(self.out/('last-frame.png' if passed else 'FAILURE.png'))
        result={'pass':passed,'test':'actual desktop Virtual Jaguar black-screen E2E','rom_sha256':hashlib.sha256(self.a.rom.read_bytes()).hexdigest(),'emulator_binary':str(self.a.emulator.resolve()),'emulator_sha256':hashlib.sha256(self.a.emulator.read_bytes()).hexdigest(),'bios':self.a.bios,'standard':self.a.standard,'mode':self.a.mode,'fresh_home_and_xdg_config':True,'isolated_x11_auto_repeat_disabled_for_physical_button_holds':True,'command':getattr(self,'command',None),'checks':self.checks,'wall_seconds':time.monotonic()-self.started,'window_captures':self.samples,'distinct_scene_hashes':len(self.scene_hashes),'black_observations_including_boot':self.black_observations,'max_completed_gpu_frame_gap_wall_seconds':self.max_gpu_gap,'watchdogs':{'boot_wall_seconds':45,'post_boot_black_wall_seconds':2,'visible_gpu_progress_wall_seconds':20,'parent_timeout_seconds':self.a.timeout},'error':error,'limitations':['Finite scenarios, not a proof of never freezing.','Actual desktop UI/keyboard/pixels only; no emulator RAM or register access.','No playability, full-conversion or hardware-compatibility claim.','20-second progress limit is a deadlock guard, not a performance target.']}
        (self.out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
        (self.out/'screens.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in self.trace))
        return result

def worker(a):
    run=None;passed=False;error=None
    try:
        run=DesktopRun(a);run.run();passed=True
    except Exception as e:
        error=type(e).__name__+': '+str(e);traceback.print_exc()
    finally:
        if run:
            run.report(passed,error);run.close()
        else:
            a.output.mkdir(parents=True,exist_ok=True);(a.output/'report.json').write_text(json.dumps({'pass':False,'error':error},indent=2))
    return 0 if passed else 1

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=R/'releases/trigger-rally-jaguar.j64')
    p.add_argument('--emulator',type=Path,default=Path(shutil.which('virtualjaguar') or '/usr/bin/virtualjaguar'))
    p.add_argument('--bios',choices=['on','off','default'],default='off')
    p.add_argument('--standard',choices=['ntsc','pal'],default='ntsc')
    p.add_argument('--mode',choices=['boot','full','watchdog'],default='full')
    p.add_argument('--output',type=Path,default=R/'artifacts/e2e-desktop')
    p.add_argument('--timeout',type=int,default=1000)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    a=p.parse_args();a.output=a.output.resolve()
    for tool in ['Xvfb','xdotool','import','xset']:
        if not shutil.which(tool):p.error('Required desktop-test dependency missing: '+tool)
    if not a.emulator.exists():p.error('Install desktop Virtual Jaguar; this test cannot be skipped')
    if a.worker:return worker(a)
    a.output.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,str(Path(__file__).resolve()),'--worker','--rom',str(a.rom.resolve()),'--emulator',str(a.emulator.resolve()),'--bios',a.bios,'--standard',a.standard,'--mode',a.mode,'--output',str(a.output),'--timeout',str(a.timeout)]
    child=subprocess.Popen(cmd,start_new_session=True)
    def interrupted(signum,frame):
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    try:
        code=child.wait(timeout=a.timeout)
    except subprocess.TimeoutExpired:
        code=124
        (a.output/'report.json').write_text(json.dumps({'pass':False,'error':'External watchdog: desktop worker did not return within '+str(a.timeout)+' seconds'},indent=2)+'\n')
    finally:
        # Always SIGKILL the group even if its parent exited after SIGTERM:
        # old Qt Virtual Jaguar can ignore SIGTERM and outlive its launcher.
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()
    print(('PASS' if code==0 else 'FAIL')+' desktop Virtual Jaguar; '+str(a.output/'report.json'),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
