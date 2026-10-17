#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Two clean native builds must equal the already E2E-tested cartridge.

Run AFTER make test; this intentionally removes/recreates build outputs.
"""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rom=R/'releases/trigger-rally-jaguar.j64';before=sha(rom)
for rel in ['artifacts/e2e-ntsc/report.json','artifacts/e2e-ntsc-bios-off/report.json','artifacts/black-screen-regression/report.json']:
    d=json.loads((R/rel).read_text());assert d['pass'] and d['rom_sha256']==before,'Run make test for the current cartridge first'
for index in [1,2]:
    with open(R/f'artifacts/native-clean-build-{index}.log','w') as log:
        for cmd in [['make','clean'],['make','-j4','all']]:subprocess.run(cmd,cwd=R,stdout=log,stderr=subprocess.STDOUT,check=True)
    assert sha(rom)==before,'REBUILD CHANGED THE ROM: rerun the E2E, do not package stale evidence'
d={'pass':True,'test':'two clean preferred-source builds equal exact E2E-tested cartridge','rom_sha256_before':before,'rom_sha256_after':sha(rom),'clean_builds_byte_identical':True,'identical_to_full_e2e_tested_rom':True}
(R/'artifacts/build-reproducibility.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d,indent=2))
