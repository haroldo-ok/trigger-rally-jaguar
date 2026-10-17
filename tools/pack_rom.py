#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Pack a real dual-boot 4 MiB Jaguar cartridge, with checked memory bounds."""
from pathlib import Path
import hashlib,json,struct
from build_inputs import fingerprint
R=Path(__file__).resolve().parents[1]
HLE_OFFSET=0x3f000
boot=(R/'src/boot.XXX').read_bytes();code=(R/'artifacts/program.bin').read_bytes();assets=(R/'assets/assets.bin').read_bytes();hle=(R/'artifacts/cartboot.bin').read_bytes()
assert len(boot)==0x410
assert len(code)+len(boot)<HLE_OFFSET, 'Code overlaps 68000 cartridge bootstrap'
assert 0<len(hle)<=0x40000-HLE_OFFSET, '68000 bootstrap overlaps asset bank'
assert struct.unpack_from('>I',code,4)[0]==0x10000
assert 0x40000+len(assets)<=0x400000, 'Assets exceed cartridge; refusing to truncate'
rom=bytearray(b'\xff'*0x400000);rom[:len(boot)]=boot
# Universal-header PC is outside the encrypted/signed GPU bootstrap bytes.
# It previously pointed at $802000, which was the middle of the linked image.
# With BIOS disabled the CPU executed garbage there and produced only black.
assert rom[0x400:0x404]==bytes.fromhex('04040404')
struct.pack_into('>I',rom,0x404,0x800000+HLE_OFFSET)
rom[0x410:0x410+len(code)]=code
rom[HLE_OFFSET:HLE_OFFSET+len(hle)]=hle
rom[0x40000:0x40000+len(assets)]=assets
p=R/'releases/trigger-rally-jaguar.j64';p.parent.mkdir(exist_ok=True);p.write_bytes(rom)
info={'rom':p.name,'rom_bytes':len(rom),'sha256':hashlib.sha256(rom).hexdigest(),'program_bytes':len(code),'asset_bytes':len(assets),'boot':'Dual path: signed GPU SBL with BIOS; native 68000 ROM-copy bootstrap without BIOS','entry_point':'0x10000','hle_entry_point':hex(0x800000+HLE_OFFSET),'hle_bootstrap_bytes':len(hle),'assets_address':'0x840000','feature_parity':'incomplete; see docs/PORT_STATUS.md','native_build_inputs_sha256':fingerprint()}
(R/'releases/build-info.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info,indent=2))
