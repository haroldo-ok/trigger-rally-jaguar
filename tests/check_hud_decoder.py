#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Decoder unit regression using authentic desktop NTSC/PAL/black captures.

These fixtures are NOT used as emulator output by the E2E. The real E2E always
starts the desktop application, sends actual keys and captures fresh windows.
"""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image
from e2e_desktop_virtual_jaguar import NativeHUD
R=Path(__file__).resolve().parents[1]
checks=[]
for name,expected in [('desktop-ntsc',3),('desktop-pal',50),('desktop-black',None)]:
    path=R/'tests/fixtures'/(name+'.png');image=np.asarray(Image.open(path).convert('RGB'))
    hud=NativeHUD();data=hud.decode(image)
    if expected is None:assert data is None,'A live desktop FPS bar is not a native title/frame counter'
    else:
        assert data is not None and data['gpu_frame']==expected,(name,data)
        assert data['rows'][1].startswith(hud.fold('TRACK:'))
        assert data['rows'][4].startswith(hud.fold('NATIVE 3D / CODE ARTEMIS + 42BASTIAN'))
    checks.append({'capture':name,'pass':True,'expected_native_gpu_frame':expected,'source_png_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'pass':True,'test':'exact native bitmap-font decoding of authentic NTSC/PAL screenshots; reject original black screen','checks':checks,'not_a_substitute_for_real_e2e':True}
(R/'artifacts/hud-decoder-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
