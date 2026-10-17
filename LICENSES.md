# Licensing and attribution

**There is no single permissive license for this entire directory or its compiled ROM.** Source code, third-party libraries/tools and original game content have different terms. Preserve their notices. This is an unofficial experimental conversion, not a release authorized by Code Artemis, Atari or 42Bastian.

## Trigger Rally source versus content — critical distinction

Upstream: <https://github.com/CodeArtemis/TriggerRally>, revision `079ac53216b74598b652ce3bf11478beb5c6832b`.

The original source code is copyright © 2012–2013 Code Artemis unless otherwise attributed, and available under **GPL v3**. Its exact License and Terms of Use are preserved in `licenses/TriggerRally-terms.md`; the complete GPL v3 is in `LICENSE` and `licenses/GPL-3.0.txt`.

The original **Content is not GPL-licensed**. Clause 3.1 prohibits modifying or redistributing it without a separate license from its owners, apart from the narrowly described local-use/own-modification provision. Repository access, asset conversion, a compiled cartridge, this document and a GPL notice on the C source do not grant those content rights. Paid content has additional conditions. **Obtain the appropriate permissions before publishing or distributing a content-bearing cartridge, converted asset bank or modified content.** Do not describe the supplied converted data or entire archive as freely redistributable.

Native game code derived from the original physics/game logic remains subject to GPL v3. New native source files carry their own SPDX headers. An `or-later` permission on a new contribution does not relicense upstream GPL-v3-only material or original content.

### Miramar skybox

The separate skybox permission is preserved in `licenses/Miramar-skybox.txt`: **Jockum Skoglund (hipshot), Stockholm, 2005-08-25**, <https://www.zfight.com/>, permits modification with credit. The skybox files are converted but are not yet used by the runtime background. This permission applies to that skybox, not to the rest of Trigger Rally.

### Missing Icarus image

The original `/a/meshes/icarus/body.jpg` reference has no corresponding file in the pinned repository. This is recorded in `assets/manifest.json`. No fabricated replacement is included; the original diffuse material colour is retained.

## 42Bastian Jaguar 3D engine

Upstream: <https://github.com/42Bastian/jag_3d_engine>, revision `f8bc66bf27346f73ec91719b62932b9ceef37d50`.

Copyright © 2026 42Bastian; **MIT**, complete notice at `licenses/jag_3d_engine-MIT.txt`. The actual GPU engine is integrated and modified under `src/gpu/`; see `docs/ENGINE_INTEGRATION.md`. The MIT attribution/permission is retained alongside the GPL game work. It does not license the original game's content.

## BJL SDK, bootloader and font

Upstream: <https://github.com/42Bastian/new_bjl>, revision `443e37c57ae779a22c33857a11fae9750646da4e`.

Open/public-domain dedication and no-warranty text: `licenses/new_bjl.txt` and `vendor/new_bjl/LICENSE`. Used for Jaguar hardware symbols/macros/video setup and the secondary-loader/font foundation. The relevant assembler includes and license are supplied under `vendor/new_bjl/`. The derived loader's complete editable source is `src/boot.js`; the pre-signed 0x410-byte blob is `src/boot.XXX`.

The optional external signing tool is the 42Bastian pc_jagcrypt fork, revision `a7d582b8097a6c185a6840e22059d3b82866b938`. It is **not bundled**. Its source retains Atari copyright notices; review that tool's terms independently. Signing a homebrew loader does not grant rights to Atari software or game content.

## lyxass assembler

Upstream: <https://github.com/42Bastian/lyxass>, revision `7bc8ad1daf4c8301a67223a9312d2d45418365d3`.

**MIT**; complete notice at `vendor/lyxass/LICENSE` and `licenses/lyxass-MIT.txt`. The complete assembler source and its build Makefile are included; the game Makefile builds it locally.

## GCC 68000 runtime

`vendor/lb1sf68.S` comes from GCC **14.2.0**, `libgcc/config/m68k/lb1sf68.S`, with its original headers retained. It contains a locally modified exact 68000 mantissa multiply. Complete source and the flags selecting each linked routine are supplied in `vendor/` and the root Makefile; `src/softfloat.c` implements target-safe conversions.

License: **GPL v3-or-later with GCC Runtime Library Exception 3.1**. Full texts: `licenses/GPL-3.0.txt` and `licenses/GCC-RUNTIME-EXCEPTION.txt`. The exception does not relicense other components/content.

## Virtual Jaguar test emulator

Upstream: <https://github.com/libretro/virtualjaguar-libretro>, revision `6bf3574c1a98ccd57719ff6b822122017b8e5942`.

**GPL v3** with retained third-party source notices; full GPL at `licenses/VirtualJaguar-GPL.txt`. Exact complete corresponding tracked source, including its own license/readme files, is supplied as `vendor/virtualjaguar-libretro-source.tar.gz`. Linux x86-64 `vendor/bin/virtualjaguar_libretro.so` was built from that revision with `make TEST_EXPORTS=1 LTO=0`; `make test-core` rebuilds from the supplied source. The test-only exports are used read-only by the actual-game frontend.

The emulator is a separate test program, not code linked into the Jaguar cartridge. Its own inclusion of BIOS support/data and any embedded third-party components remains subject to their respective retained notices. No physical Atari hardware or retail cartridge image is included as a project input.

## External build/conversion dependencies

GNU Make/GCC/binutils, Python, NumPy, SciPy, Pillow, ffmpeg and optional desktop Virtual Jaguar are separately installed tools, not relicensed or bundled by this project. Consult their respective licenses when redistributing those tools. Tested versions are recorded in `artifacts/tool-versions.json`.

## No warranty or completion claim

The ROM and source are unfinished and far too slow to play normally. Test passes establish only the finite recorded regression scenarios. They do not warrant full compatibility, physical-hardware operation, full original feature/asset parity, or any redistribution permission.


## Native DSP build-tool sources added for the driving correction

`vendor/jrisc/sources.json` records exact SHA-256 hashes and provenance for the
**unmodified** vbcc, VASM and vlink source archives. The toolchain is built only
in `.cache/jrisc/`; the project compiler/scheduler changes are distributed as
`tools/patches/vbcc-jrisc-binary32.patch`, not as a modified upstream archive.

vbcc is source-available and permits non-commercial use under its original
terms; other commercial use needs the author's written consent. Do not assume
that the compiler is GPL merely because the game's source is GPL. See the legal
section of `vbcc/doc/vbcc.texi` inside the unchanged archive and
`vendor/jrisc/UPSTREAM-README.txt`. VASM and vlink have their own terms preserved
inside their source archives as well.

**No vbcc C runtime is linked into the game.** The DSP arithmetic/matrix runtime
and 68000 host added here are project GPL code; the independently compiled GCC
runtime remains for the legacy 68000 arithmetic unit. Original game-content
restrictions and missing-asset notices elsewhere in this document still apply.
