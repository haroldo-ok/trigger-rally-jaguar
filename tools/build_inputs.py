#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Content hashes of actual native-build inputs, independent of timestamps."""
from pathlib import Path
import hashlib
R=Path(__file__).resolve().parents[1]
def fingerprint():
    paths={R/'Makefile',R/'vendor/lb1sf68.S',R/'vendor/revisions.json'}
    paths.update(p for p in (R/'src').rglob('*') if p.is_file() and p.suffix not in {'.o','.pyc','.P','.elf'})
    paths.update(R/'assets'/n for n in ['assets.bin','gpu.bin','audio.bin','dsp_game.bin','asset_ids.h','asset_ids.inc','memory.json'])
    paths.update(R/'tools'/n for n in ['build_inputs.py','pack_rom.py','make_obl.py','memory_map.py','convert_assets.py','cry_palette.json','build_dsp_game.py','build_jrisc_tools.py','make_render_tables.py'])
    paths.update(p for p in (R/'vendor/jrisc').rglob('*') if p.is_file())
    paths.update(p for p in (R/'tools/patches').glob('*') if p.is_file())
    paths.update(p for p in (R/'vendor/lyxass').iterdir() if p.suffix in {'.c','.h'} or p.name=='Makefile')
    paths.update(p for p in (R/'vendor/new_bjl/js').rglob('*') if p.is_file() and p.suffix in {'.js','.mac','.inc','.bin','.h'})
    return {str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
