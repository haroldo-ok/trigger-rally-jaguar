#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Launch the actual cartridge with an absolute path and GPU/DSP enabled.

The ROM itself supports both BIOS paths. This is not a BIOS-forcing workaround.
Desktop Virtual Jaguar 2.1.3 default keys: L/K/J = Jaguar A/B/C; S/Z/X/C=d-pad.
"""
from pathlib import Path
import argparse,os,shutil,subprocess
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('rom',nargs='?',type=Path,default=R/'releases/trigger-rally-jaguar.j64')
p.add_argument('--emulator',default=shutil.which('virtualjaguar'))
p.add_argument('--bios',choices=['auto','on','off'],default='auto')
p.add_argument('--standard',choices=['ntsc','pal'],default='ntsc')
a=p.parse_args()
if not a.emulator:p.error('Install Virtual Jaguar or supply --emulator=/path/to/virtualjaguar')
if not a.rom.is_file():p.error('Cartridge not found: '+str(a.rom))
command=[a.emulator,str(a.rom.resolve()),'--gpu','--dsp','--no-blur','--'+a.standard]
if a.bios!='auto':command.append('--bios' if a.bios=='on' else '--no-bios')
e=dict(os.environ)
for key in ['QT_QPA_PLATFORM_PLUGIN_PATH','QT_QPA_FONTDIR']:
    if '/cv2/' in e.get(key,''):e.pop(key)
print('Launching actual ROM:',a.rom.resolve(),flush=True)
print('Default desktop keys: L=start/throttle, K=brake, J=handbrake, P=pause, O=menu.',flush=True)
raise SystemExit(subprocess.run(command,env=e).returncode)
