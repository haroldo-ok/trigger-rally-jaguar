# Build and reproduction

## Tested host and normal cartridge build

Linux, Python 3.12+, GNU Make 4.3+, a native C compiler, `m68k-linux-gnu-gcc` and `m68k-linux-gnu-objcopy` are the supported build path. The recorded environment uses m68k GCC 14.2. Other compilers/hosts require independent verification.

```sh
sudo apt-get install build-essential gcc-m68k-linux-gnu binutils-m68k-linux-gnu python3-venv
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
make -j4 all
python3 tests/check_assets.py
```

Output: `releases/trigger-rally-jaguar.j64`, exactly 4,194,304 bytes. `releases/build-info.json` records its actual SHA-256, sizes and content hashes of native build inputs. The packer checks the signed/header bytes, genuine boot entries, copy/bootstrap bounds and cartridge capacity; it refuses truncation.

A normal source-package build uses the included converted asset bank/font/signed loader. It needs no network fetch or original-asset regeneration. Generated code/objects/emulator executables are not source-package inputs.

## Native architecture and preferred build inputs

- **68000:** `src/start.S`, `src/host.c`, `src/dsp_blob.S`, `src/jaguar.ld` and `src/cartboot.S` implement actual cartridge startup, ROM-to-RAM copying and DSP launch. The signed SBL and `$83F000` HLE copy entry remain; a genuine compatibility jump is placed at cartridge `$802000`.
- **DSP:** `src/main.c`, `src/physics.c`, `src/render_math.c` and `src/dsp/` implement the actual game/50-Hz physics/audio and local binary32 arithmetic. `tools/build_dsp_game.py` generates `assets/dsp_game.bin` and its address header.
- **GPU:** actual adapted 42Bastian `jag_3d_engine` sources under `src/gpu/`. `tools/make_obl.py` reproduces its 128-byte PAL/NTSC OP lists and PAL-safe HUD positioning.
- **JRISC tools:** `vendor/jrisc/` contains checksum-pinned **unmodified** compiler/assembler/linker source archives. `tools/build_jrisc_tools.py` builds them in `.cache/jrisc/`, applying the separately supplied project patch. Source-available vbcc has non-commercial-use terms; obtain the author's permission for other commercial tool use. See `LICENSES.md` and upstream archive terms. No vbcc runtime library is linked into the game.
- **lyxass/BJL:** `vendor/lyxass/` and `vendor/new_bjl/` provide the actual assembler and SDK symbols/macros used by the renderer/loader. They are built/included locally.
- **Legacy 68000 math unit:** `vendor/lb1sf68.S` and `src/softfloat.c` remain for independent actual-68000 arithmetic validation. Do not link an arbitrary distribution `-lgcc`: earlier distribution objects required 68881/68020 instructions unavailable on Jaguar. Production game physics now runs on Jerry, not that old 68000 solver path.

`make clean` removes native compiled/linked outputs, generated GPU/DSP binaries and the DSP address header, while retaining converted source data and test reports. A following `make all` recompiles native sources. If changing the compiler patch itself, delete `.cache/jrisc/` to rebuild its private tools from the unchanged archives.

`tools/memory_map.py` is the paired C/GPU memory-map source. Structure tests guard tool/runtime bounds, caches, replay allocation, DSP stacks and the embedded DSP image against overlaps.

## Regenerate original content

Read `licenses/TriggerRally-terms.md` first: content is **not GPL** and this procedure grants no publication rights.

```sh
sudo apt-get install git ffmpeg
make fetch-upstream
make regenerate-assets TR_PUBLIC="$PWD/.cache/TriggerRally/server/public"
make -j4 all
```

`fetch_upstream.py` obtains the exact revision in `vendor/revisions.json` and refuses to silently replace a different checkout. Alternatively supply `TR_PUBLIC` pointing at a pinned `server/public` tree.

The converter decodes source Three.js face flags, material/UV references, scene-child transforms and full mesh topology; derives native LODs; bakes original checkpoint geometry and vegetation material; converts course/deformation/height data, car configs, authored scenery, textures and all original Ogg samples. `assets/manifest.json` records every consumed input hash, missing source references and known adaptations. This is not full editor/network/world/fidelity parity; see `PORT_STATUS.md`.

Pillow/SciPy/ffmpeg version changes can alter converted output. Re-run all gates after regeneration. Native render-only sine tables are reproducible with `python3 tools/make_render_tables.py`.

## Optional signed-loader regeneration

Normal builds use deterministic `src/boot.XXX` with complete editable `src/boot.js`, derived from the BJL secondary loader.

Re-signing needs the 42Bastian fork of pc_jagcrypt, not the older parent lacking `-tursi`:

```sh
git clone https://github.com/42Bastian/pc_jagcrypt.git /path/to/pc_jagcrypt
git -C /path/to/pc_jagcrypt checkout a7d582b8097a6c185a6840e22059d3b82866b938
make -C /path/to/pc_jagcrypt
JAGCRYPT=/path/to/pc_jagcrypt/jagcrypt make bootstrap
make all
```

The loader publishes the CPU destination after copying the payload and avoids a disabled-interrupt-dependent boot wait. Retail game ROMs are not native build inputs.

## Rebuild the real emulator test core

Source distributions intentionally omit `vendor/bin/virtualjaguar_libretro.so`. Build it first:

```sh
make test-core
```

This extracts the pinned `6bf3574c1a98ccd57719ff6b822122017b8e5942` sources into `.cache/virtualjaguar-libretro` and uses `TEST_EXPORTS=1 LTO=0`. Test exports expose real emulated memory/PCs, used **read-only**. Game loading/video/audio/input are standard libretro calls.

The compact source snapshot removes optional website artwork and precompiled test images, not build/license/source contents. The delivered preferred-source extraction is checked by actually compiling that snapshot and booting/driving the rebuilt cartridge. A Git-less build can have a different version-stamp/binary hash from the originally tested Git-checkout core. Each report is valid only for its recorded core; after changing the core, rerun tests.

```sh
make test CORE="$PWD/vendor/bin/virtualjaguar_libretro.so"
```

The automated target is Linux-specific and copies a `.so`; other OS/CPU/ABI platforms need upstream build options and adapted output handling.

## Test and gated packaging

```sh
sudo apt-get install virtualjaguar xvfb xdotool imagemagick libgl1-mesa-dri x11-xserver-utils
make test
python3 tools/check_reproducibility.py
(cd releases && sha256sum trigger-rally-jaguar.j64 > ROM.sha256)
make release
python3 tools/check_packaged_build.py
make release   # adds only extraction/rebuild/boot/driving proof
```

The gate requires exact-ROM/current-core driving, full desktop/core/safety/causal checks, numeric/structure checks and two clean native builds. Smoke mode is not release authorization. The compact DRIVABLE ZIP contains only the current actual game cartridge, not unit/fault/old game ROMs or a prebuilt emulator. Its manifest hashes every entry.

The extracted-delivery check builds both preferred native toolchains/game and the filtered emulator source, reproduces the exact cartridge and runs real BIOS-off boot/reset plus Base driving/finish. That is separate from the full matrix on the originally tested core.

## Limits

Enable GPU and DSP. Do not change emulator clocks to make a regression pass. The production game uses main RAM for DSP C code with the compiler's documented main-memory workarounds and local RAM for hot arithmetic/audio; physical hardware is untested. A flat freestanding 68000 linker RWX-segment warning is not hidden and is not a hardware certification.

Driving gates establish bounded low-frame-rate racing, not full original feature parity, every collision/flight path, every emulator setting or a literal never-freeze guarantee. Native cache/replay/stack addresses are documented in `assets/memory.json` and checked structurally.
