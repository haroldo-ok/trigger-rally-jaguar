# Real Virtual Jaguar tests

The previous suite forced BIOS on and missed a real BIOS-disabled cartridge-entry bug. That limitation is corrected, not hidden. See [BLACK_SCREEN_REGRESSION.md](BLACK_SCREEN_REGRESSION.md) for the reproduction, native dual-boot fix, desktop details, negative controls and CI/release gate.

## Driving is a separate acceptance gate

`make test-driving` runs `tests/playability_suite.py`: all three courses/both cars in NTSC, both Base cars in PAL, real-time countdown and race clock, minimum physical displacement/speed, live changing 3D video, completed-frame floors, measurable braking/heading change and pause. Base/car0 must actually finish by ordered checkpoint driving, never by replay. Zero-engine-power and native delayed-racing cartridges must fail the intended movement/timing guard. See [PLAYABILITY.md](PLAYABILITY.md).

The DSP now runs the actual game/physics/audio while the 68000 is its bootstrap host. The legacy CPU-frame telemetry word means completed native game submissions, not executing 68000 instructions. New signed Q16 forward X/Y words are appended at offsets 72/76. No test writes target state.

## Commands

```sh
make test-driving       # real-time acceleration/braking/steering/finish and specific controls
make test-black-screen  # actual GUI gameplay + 13 configurations + five real fault controls
make test               # plus native structure/arithmetic and full core interaction, BOTH BIOS paths
make test-smoke         # shorter boot/menu/reset matrix, NOT full gameplay or release authorization
make test-desktop       # separately run actual desktop NTSC BIOS-off full gameplay
```

No required frontend/dependency is silently skipped. The desktop test needs installed `virtualjaguar`, `Xvfb`, `xdotool`, ImageMagick `import`, OpenCV, NumPy and Pillow. The core test needs the actual libretro `.so`, NumPy/Pillow and its read-only debug exports; source is supplied; source packages deliberately omit the prebuilt `.so`, so run `make test-core` first.

Direct configuration examples:

```sh
python3 tests/e2e_desktop_virtual_jaguar.py --bios off --standard ntsc --mode full
python3 tests/e2e_desktop_virtual_jaguar.py --bios on --standard pal --mode boot
python3 tests/e2e_virtual_jaguar.py --bios off --blitter accurate --mode full --output artifacts/e2e-ntsc-bios-off
python3 tests/black_screen_suite.py
```

## Actual desktop application — not a screenshot mock

`tests/e2e_desktop_virtual_jaguar.py` creates an isolated Xvfb display and fresh HOME/XDG settings/NVRAM. It starts the actual Qt desktop executable with an absolute cartridge path, GPU/DSP enabled, accurate blitter and the requested standard/BIOS path. The default-BIOS case leaves the BIOS preference unspecified. It seeds the stock controller bindings and known UI placement/filtering only.

The test captures the actual window and sends real keyboard/mouse input. It does not read/write emulator process memory. It requires a multicolour, horizontally detailed 3D scene, decodes the game's own bitmap font and observes its **native completed GPU-frame counter**, never the emulator FPS status bar. Exact nearest-neighbour phases/pixel origins differ between PAL/NTSC and across the viewport; the decoder accepts those exact rasterizations without weakening the match threshold. `check_hud_decoder.py` separately checks authentic NTSC/PAL/black screenshot fixtures; fixtures are **never** substituted for live E2E video.

Full mode checks all six menu selections, idle progress, countdown, racing/clock/speed/scene motion under throttle, pause with frozen clock but live renderer, resume, menu and actual emulator power cycle/counter reset/renewed progress. Fifteen checkpoints must pass. Desktop keys: **L/K/J = Jaguar A/B/C**, S/Z/X/C = d-pad up/left/down/right, P = Pause, O = Option.

## Actual core full-game interaction

`tests/e2e_virtual_jaguar.py` loads the actual cartridge in the real Virtual Jaguar libretro core, at normal clocks. Accurate blitter is the default. BIOS on/off are explicit independent configurations. Inputs are standard libretro joypad callbacks; framebuffers and audio are standard callbacks. Memory/PC diagnostics are **read-only**; no test writes native position, state, checkpoints, time, inputs or a fake success flag.

Each of the two full NTSC BIOS-path runs requires 21 checks:

- Cold native boot, expected telemetry signature/state and native CPU/GPU progress.
- All 3 tracks × 2 cars, actual course rendering changes and idle soak.
- Native countdown → racing; throttle-driven motion, speed, checkpoint progress and recorded poses.
- Pause with stable simulation position/time but live GPU rendering, then resume.
- Steering/camera/brake input and RAM replay through completion.
- Restart, alternate-course live simulation, final menu soak.
- Console reset, a reset native frame counter and renewed native/GPU progress.

Replay completion is not full-course driving/finish. The limited replay records poses in RAM; it does not prove source-game replay parity.

## Core read-only diagnostics

Native telemetry lives at RAM `$1000`; offsets below are big-endian 32-bit words:

| Offset | Meaning |
|---|---|
| 0 | Native signature `TRJ1` |
| 4 | CPU/GPU scene command/handshake |
| 8 / 12 / 16 | VBL / completed GPU / CPU frames |
| 20 / 24 / 28 | Native state / track / car |
| 32 / 36 / 40 | Checkpoint / race time / speed |
| 44 / 48 / 52 | Native world position |
| 56 / 60 / 64 / 68 | Error flags / scanned inputs / recorded replay poses / state flags |

States: menu 0, countdown 1, racing 2, paused 3, finished 4, replay 5. The monitor also checks pixel colour/diversity/horizontal variation, distinct scene hashes, framebuffer bounds, actual audio output, CPU/GPU progress, math-fault telemetry and invariants. A live VBL alone is never success.

## Watchdogs and real faulty cartridges

Desktop: 45 wall-clock seconds for boot, 2 seconds of black/empty scene after boot, 20 seconds without visible native GPU progress, and an external normally 1,000-second process-tree watchdog. Negative controls use a 90-second outer bound. Core: 600 emulated boot frames, 2 emulated seconds of black and 15 emulated seconds without native CPU/GPU progress, plus an external wall-clock deadline. The slow port's progress allowance is **not** acceptable frame-rate performance.

The suite rejects five specific actual cartridge faults: infinite entry branch through each core BIOS path, infinite entry in the desktop, native VRAM/HUD clear after eight completed GPU frames, and a native CPU-loop freeze after eight frames with the last scene left visible. The normal game is not modified. Temporary faulty images live only in `.cache`. A negative worker intentionally has `pass: false`/nonzero exit; it passes as a control only if the intended error string matches, and post-boot controls must first have visibly booted. Missing dependencies or unrelated crashes do not count as detecting a fault.

A separate historical-entry control reverts only the universal-header PC. The same actual game must boot with BIOS on and be rejected with BIOS off in both frontends; it catches an accidentally BIOS-forced harness. The core requires boot timeout; the old desktop may instead terminate before boot on malformed entry (observed native exit status 0, also allowing native SIGSEGV), recorded before cleanup with no successful native checkpoint. This is distinct from accepting an unrelated Python/xdotool/startup error by itself. See `artifacts/bios-path-regression/report.json`. The five watchdog controls above remain strictly reason-matched.

## Evidence / exact-ROM release gate

- `artifacts/black-screen-regression/report.json`: 13 normal configurations + five expected-failure controls, ROM/emulator/test-source hashes.
- `artifacts/black-screen-regression/*/report.json`: fresh-process evidence and screenshots; full desktop is `desktop-ntsc-bios-off`.
- `artifacts/e2e-ntsc/report.json`, `artifacts/e2e-ntsc-bios-off/report.json`: both full accurate-core paths.
- `artifacts/hud-decoder-report.json`, `math-report.json`, `asset-report.json`: decoder/real 68000 arithmetic/native structure checks.
- `artifacts/build-reproducibility.json`: two clean builds must reproduce the exact E2E-tested ROM.
- `artifacts/packaged-build-report.json`: extracted-source build and actual BIOS-off boot/reset proof.

```sh
make test
python3 tools/check_reproducibility.py
python3 tools/verify_release.py
make release
python3 tools/check_packaged_build.py
make release  # include extracted-package proof/logs, unchanged source/ROM payload
```

The packer requires the **full default matrix**, not smoke, both full core paths and full actual desktop gameplay for the exact cartridge hash. Current test-source hashes and native-build input hashes must match. Changed sources, failed/incomplete runs or an earlier ROM's report block delivery. `.github/workflows/virtual-jaguar-e2e.yml` runs builds/tests on pushes and pull requests; configure it as a required repository check to enforce merge blocking.

No finite test establishes “never freezes,” full Trigger Rally conversion, all emulator versions/settings, long-session stability, acceptable performance or physical Jaguar compatibility. These remain explicit limits in `PORT_STATUS.md`.


## Post-boot fault observation

The accelerated DSP build can reach eight game frames before a desktop font locator has established its boot checkpoint. Post-boot black/freeze controls therefore require both eight completed frames and an eight-second native VBL interval before triggering. An explicit `--mode watchdog` uses the same window capture and exact black/frozen-frame watchdogs, allows the healthy boot/soak checkpoint first, then watches long enough for the specific fault rejection. The 2-second black / 20-second frozen-scene limits are unchanged; generic soak/dependency/compiler errors do not count as intended controls.

A new genuine compatibility jump makes `$802000` a safe entry. The causal malformed-header test now points only the universal-header PC **past that jump into DSP data at `$802010`**: BIOS-on must still boot and BIOS-off must be rejected. The healthy game is tested separately with unforced and explicit BIOS settings.


## Stable held-button input on X11

The isolated Xvfb display disables X11 auto-repeat with `xset r off` before launching the actual emulator. A real Jaguar button is continuously held until released; OS-generated repeat key-up/key-down pairs can otherwise toggle a menu selection twice while a slow window capture is in progress. One PAL BIOS-on run exposed this: GPU/scene stayed healthy, the requested car briefly appeared, then a repeat edge selected the previous car. It was an input-state timeout, not a black/frozen game. No match/watchdog threshold was weakened, and the complete matrix is rerun after making the test's physical-button holds deterministic. The user's real display/settings are never modified.
