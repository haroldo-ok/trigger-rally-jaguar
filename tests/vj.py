# SPDX-License-Identifier: GPL-3.0-only
"""Minimal headless frontend to the REAL Virtual Jaguar libretro core.

No game rendering, simulation, memory patching, or fake telemetry is performed
here. Only standard libretro video/audio/input callbacks and read-only debug
access to emulated memory. A fresh process is required for each emulator run.
"""
from __future__ import annotations
import ctypes as C
from pathlib import Path
import struct,tempfile
import numpy as np
from PIL import Image

class Info(C.Structure):
    _fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class Variable(C.Structure):
    _fields_=[('key',C.c_char_p),('value',C.c_char_p)]
ENV=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p)
VIDEO=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t)
AUDIO=C.CFUNCTYPE(None,C.c_int16,C.c_int16)
BATCH=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t)
POLL=C.CFUNCTYPE(None)
INPUT=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
class VJ:
    def __init__(self,core,rom,pal=False,bios=True,fastblitter=False):
        self.lib=C.CDLL(str(Path(core).resolve()));self.frame=0;self.buttons=set();self.image=None;self.audio_peak=0;self.audio_nonzero=0;self.audio_samples=0;self.video_calls=0
        self.options={b'virtualjaguar_bios':b'enabled' if bios else b'disabled',b'virtualjaguar_pal':b'enabled' if pal else b'disabled',b'virtualjaguar_usefastblitter':b'enabled' if fastblitter else b'disabled',b'virtualjaguar_dsp':b'enabled'}
        # No saved EEPROM/profile/NVRAM from a preceding test may mask cold boot.
        self._save=tempfile.TemporaryDirectory(prefix='virtualjaguar-core-')
        self.directory=self._save.name.encode()
        def env(cmd,p):
            cmd&=~0x10000
            if cmd==15:
                v=C.cast(p,C.POINTER(Variable)).contents
                if v.key in self.options:v.value=self.options[v.key];return True
                return False
            if cmd in (9,31):C.cast(p,C.POINTER(C.c_char_p))[0]=self.directory;return True
            if cmd==10:return C.cast(p,C.POINTER(C.c_int))[0]==1
            if cmd==17:C.cast(p,C.POINTER(C.c_bool))[0]=False;return True
            if cmd==3:C.cast(p,C.POINTER(C.c_bool))[0]=True;return True
            if cmd==52:C.cast(p,C.POINTER(C.c_uint))[0]=0;return True
            if cmd in (11,16,18,35):return True
            return False
        def video(p,w,h,pitch):
            self.video_calls+=1
            if not p:return
            a=np.frombuffer(C.string_at(p,pitch*h),dtype=np.uint8).reshape(h,pitch)[:,:w*4].reshape(h,w,4)
            self.image=a[:,:,[2,1,0]].copy()
        def batch(p,n):
            a=np.frombuffer(C.string_at(p,n*4),dtype=np.int16).astype(np.int32)
            self.audio_samples+=n;self.audio_nonzero+=int(np.count_nonzero(a));self.audio_peak=max(self.audio_peak,int(np.abs(a).max(initial=0)));return n
        def inp(port,device,index,id):
            if port or device!=1:return 0
            if id==256:return sum(1<<b for b in self.buttons)
            return int(id in self.buttons)
        self.callbacks=[ENV(env),VIDEO(video),AUDIO(lambda l,r:None),BATCH(batch),POLL(lambda:None),INPUT(inp)]
        for name,cb in zip(('environment','video_refresh','audio_sample','audio_sample_batch','input_poll','input_state'),self.callbacks):getattr(self.lib,'retro_set_'+name)(cb)
        self.lib.retro_init()
        self.rom_data=C.create_string_buffer(Path(rom).read_bytes());self.rom_path=str(Path(rom).resolve()).encode()
        info=Info(self.rom_path,C.cast(self.rom_data,C.c_void_p),len(self.rom_data)-1,None)
        self.lib.retro_load_game.restype=C.c_bool
        if not self.lib.retro_load_game(C.byref(info)):raise RuntimeError('Virtual Jaguar refused ROM')
        self.lib.retro_get_memory_data.restype=C.c_void_p
        self.ram=self.lib.retro_get_memory_data(2)
        if not self.ram:self.ram=C.addressof((C.c_ubyte*0x200000).in_dll(self.lib,'jaguarMainRAM'))
        self.lib.m68k_get_reg.argtypes=[C.c_void_p,C.c_int];self.lib.m68k_get_reg.restype=C.c_uint
        self.lib.GPUGetPC.restype=C.c_uint
    def read(self,address,size):return C.string_at(self.ram+address,size)
    def u32(self,address):return struct.unpack('>I',self.read(address,4))[0]
    def i32(self,address):return struct.unpack('>i',self.read(address,4))[0]
    def telemetry(self):
        keys=['magic','command','vbl','gpu_frames','cpu_frames','state','track','car','checkpoint','time_ms','speed_q16','x_q16','y_q16','z_q16','error','input','recorded_frames','flags']
        d=dict(zip(keys,struct.unpack('>18I',self.read(0x1000,72))))
        for k in ['x_q16','y_q16','z_q16']:d[k]=struct.unpack('>i',struct.pack('>I',d[k]))[0]
        return d
    def step(self,n=1,buttons=None):
        if buttons is not None:self.buttons=set(buttons)
        for _ in range(n):self.lib.retro_run();self.frame+=1
    def debug(self):return {'frame':self.frame,'cpu_pc':hex(self.lib.m68k_get_reg(None,16)),'gpu_pc':hex(self.lib.GPUGetPC()),'telemetry':self.telemetry()}
    def save(self,path):
        if self.image is None:raise RuntimeError('No framebuffer received')
        Image.fromarray(self.image).save(path)
    def reset(self):self.lib.retro_reset()
    def close(self):
        self.lib.retro_unload_game();self.lib.retro_deinit();self._save.cleanup()
