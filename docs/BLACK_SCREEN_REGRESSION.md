# Black-screen regression: reproduced, fixed, and release-gated

> **2026-10-16 driving update:** the game now runs on the DSP with a 68000 bootstrap host and parallel GPU rendering; see `PLAYABILITY.md`. The historical reproduction/fix below remains valid evidence for the earlier cartridges. The current cartridge additionally has a real compatibility `JMP $83F000` at `$802000`, so that old address is now safe. The current paired malformed-header control uses `$802010` instead, without forcing BIOS settings. Post-boot controls allow a healthy native VBL interval before exact black/frozen watchdog observation; their thresholds are unchanged.

## What was wrong with the previous delivery

Previous ROM SHA-256:

`27f0b8d7dd0ddbf1d353544503ca857657839851781ef2a397cbd4ca62592337`

With **BIOS disabled**, its cartridge universal-header PC at offset `$404` pointed to **`$802000`**. That is the middle of the native program image, not a cartridge startup routine. The actual game's program must first be copied from ROM `$800410` to RAM `$10000`. Without the signed BIOS/GPU loader, that copy never happened, so the CPU executed unrelated bytes, the native telemetry signature stayed zero and the framebuffer stayed black.

This was reproduced in **both** the actual desktop Virtual Jaguar 2.1.3 application and the real libretro core. The desktop continued reporting roughly 60 emulator FPS while displaying black. A 660-frame core probe showed no native CPU/GPU frames and a completely black framebuffer. Evidence is under `artifacts/black-screen-investigation/`.

The prior automated test forced BIOS **on**, and the prior desktop check was manual and also used `--bios`. Consequently, its pass did not cover this launch configuration. Those old results did not justify claiming the delivered ROM was protected against this black screen.

This is a reproduced failure path; without the user's exact emulator/version/settings, it is not proof that every reported black screen has this same cause.

## Actual cartridge fix — not just a launcher workaround

- The signed 42Bastian-derived GPU bootstrap is retained, unchanged in its encrypted/signed bytes, for BIOS boot.
- The universal-header PC now points to a real **68000 ROM bootstrap at `$83F000`**.
- `src/cartboot.S` disables interrupts, stops leftover GPU/DSP jobs, copies the same native payload to the destination specified in its header, and jumps to it. Both boot paths run the **same game code**, not different demos.
- The packer checks that the program, bootstrap and asset bank do not overlap. Assets remain at `$840000`; native entry remains `$10000`.
- The title HUD now exposes the actual completed **GPU scene-frame counter in every game state**. It is not the emulator refresh/VBL counter.
- The first actual PAL desktop matrix caught the title/counter being clipped above the visible region. PAL HUD start is now 42 rather than 30 scanlines; scene placement is unchanged. `tools/make_obl.py` regenerates both PAL/NTSC object lists from source. Only four ROM payload bytes changed in this additional native layout fix; the final cartridge was fully retested rather than reusing the earlier hash's pass.

`--bios` is no longer a required workaround. BIOS-on and BIOS-off launches are independently tested. Physical Jaguar hardware remains untested.

## One-command regression

Install the normal build requirements plus the actual desktop emulator/test tools:

```sh
sudo apt-get install virtualjaguar xvfb xdotool imagemagick libgl1-mesa-dri
pip install -r requirements.txt
make test-black-screen
```

Equivalent direct command after building:

```sh
python3 tests/black_screen_suite.py
```

This is a real E2E, not a simulated game or mocked emulator. It fails if dependencies are missing; it does not silently skip desktop tests.

For the complete physics/replay interaction tests as well:

```sh
make test
```

For a shorter boot/menu/reset matrix without desktop racing:

```sh
python3 tests/black_screen_suite.py --smoke
```

**Smoke is not full gameplay coverage and cannot authorize a release.** The packer requires the full default matrix, including desktop gameplay, plus both full core paths.

The existing slow port makes full gameplay tests take minutes. The guard limits distinguish black-screen/deadlock detection from performance acceptance; performance is still unplayable.

## Desktop: the actual GUI application

`tests/e2e_desktop_virtual_jaguar.py` starts the installed **desktop Virtual Jaguar executable** on its own Xvfb display. Every case gets new HOME/XDG settings/NVRAM, an absolute ROM path, GPU/DSP enabled, and the specified video/BIOS mode. It does not inherit the developer's successful emulator profile.

It captures the actual emulator window, locates the native title by matching the game's own 8×8 font, and reads its visible GPU-frame count. Both exact nearest-neighbour sampling phases and one-pixel sample-origin changes are handled because the desktop version rescales 384-wide video into non-square pixels. Authentic NTSC/PAL/black captures also have an independent decoder regression; they are never used as live E2E output. There is no host-generated scene, fake video, host-side physics, process-memory patch, native-state patch or assumed success based on emulator FPS.

Required observations:

1. A native menu **and a nonblack, horizontally detailed, multicolour 3D scene**, not just a live desktop/status bar.
2. The visible completed GPU-frame number advances during an idle soak.
3. Actual keyboard/controller input selects all six track/car combinations. Changing course must change the scene, not just its label.
4. In full mode: native countdown → racing, advancing race clock and speed, changed scene under throttle, pause with a stable race clock and continuing GPU rendering, resume and return to menu.
5. The actual emulator power button is cycled. The GPU counter must restart below its previous value, then advance again; a stale screenshot cannot satisfy this check.

The confirmed desktop 2.1.3 default keys are **S/Z/X/C** for up/left/down/right, **L/K/J** for Jaguar **A/B/C**, **P** for Pause and **O** for Option. In particular, **L is throttle/start**, not J. The earlier documentation's A/C keyboard mapping was reversed and has been corrected.

## Configuration matrix

Thirteen normal cases:

| Frontend | BIOS | Video | Blitter | Coverage |
|---|---|---|---|---|
| Actual desktop GUI | off | NTSC | accurate/default | Full gameplay in the normal suite; boot/menu/reset in smoke mode |
| Actual desktop GUI | on | NTSC | accurate/default | Boot, live idle, six selections, power cycle |
| Actual desktop GUI | on/off | PAL | accurate/default | Same boot/menu/reset checks, separate fresh processes |
| Actual desktop GUI | untouched fresh default | NTSC | accurate/default | No forced BIOS flag or inherited BIOS preference |
| Actual libretro core | on/off | NTSC/PAL | accurate/fast | Eight cold-boot/idle/console-reset combinations |

Additionally, the full read-only-telemetry core interaction test was run separately with **both BIOS on and BIOS off**, including real motion/checkpoint progress, pause/resume, steering/camera/brake, RAM replay completion, restart, alternate tracks and console reset.

## Prove the test fails on bad cartridges

Five negative cases use actual cartridge files and the **same unmodified E2E harnesses**:

- Infinite native entry branch, core BIOS **on**: must fail its boot deadline.
- Infinite native entry branch, core BIOS **off**: must fail its boot deadline.
- Infinite native entry branch, desktop: must be rejected as `BLACK_BOOT`.
- A compiled copy of the actual game clears both framebuffers and HUD after **eight completed GPU frames**, then stops: must be rejected as `BLACK_SCREEN` after two seconds of black.
- A compiled copy stops its native game loop after **eight GPU frames**, leaving the last scene visible: must be rejected as `FROZEN_GAME` when the visible GPU counter stops progressing, even if emulator FPS stays normal.

`tests/make_fault_rom.py` builds these controls without changing the released cartridge. They are kept in `.cache`, never packaged as the game. Negative worker `report.json` files intentionally say `pass: false`; the suite reports a passing control only if the **specific intended watchdog error** occurs. A missing emulator, import failure or unrelated crash is not accepted as detecting the fault.

## A control specifically for the original missed BIOS path

`tools/check_bios_path_regression.py` is also included in `make test-black-screen` and `make test`. It copies the **current actual cartridge** and reverts only the universal-header PC to `$802000`, preserving the valid signed loader and all native game/asset bytes. The same file must **boot with BIOS on** and **be rejected with BIOS off**, independently in both frontends. A test frontend accidentally forcing BIOS on would fail this asymmetric control, rather than making both nominal paths green.

The core must report its boot timeout. Desktop 2.1.3 was also observed to terminate with status 0 before native boot on the malformed entry; it need not remain black until the deadline. For this historical-input control only, the helper runs the **same unchanged desktop E2E class** and records the actual native emulator process return code before cleanup: only `BLACK_BOOT`, or an observed native-app exit (status 0 / SIGSEGV) **before any native boot checkpoint**, is accepted for this causal probe. A generic xdotool, dependency, Qt startup or Python-worker error without that recorded native termination is not accepted. Native status 0 is not game success: the standard E2E still returns nonzero if no game booted. The same-fault BIOS-on pass and normal-game BIOS-off pass supply healthy controls. This does not relax the five separately reason-matched watchdog controls above.

Evidence: `artifacts/bios-path-regression/report.json` and its four child reports. This is additional to the 13-configuration/five-fault matrix, not silently included in those counts.

## Watchdogs and evidence

Desktop limits:

- Boot: 45 wall-clock seconds.
- Post-boot black/empty scene: 2 wall-clock seconds.
- Visible native GPU progress: 20 wall-clock seconds.
- Worker: bounded external timeout, normally 1,000 seconds; negative cases 90 seconds.

Core limits remain 600 emulated frames for boot, 2 emulated seconds of black/empty scene, and 15 emulated seconds without native CPU/GPU progress. Each worker also has an external wall-clock timeout. The desktop parent kills the complete worker/emulator/display process group on failure/timeout; old Qt processes cannot survive a terminated launcher and make a later test look alive.

Reports include the actual ROM/emulator hashes, settings, screenshots, native frame progress, errors and finite coverage:

- `artifacts/black-screen-regression/report.json` — matrix/control summary.
- `artifacts/black-screen-regression/*/report.json` — each fresh-process case.
- `artifacts/black-screen-regression/desktop-ntsc-bios-off/report.json` — full desktop gameplay inside the default suite. `make test-desktop` can additionally write a separate `artifacts/e2e-desktop-ntsc-bios-off/report.json`.
- `artifacts/e2e-ntsc/report.json` and `artifacts/e2e-ntsc-bios-off/report.json` — both full core paths.

## CI/release gate, and the limit of “ever again”

`.github/workflows/virtual-jaguar-e2e.yml` supplies an automated build/test job for pushes and pull requests. It installs the real emulators, rebuilds the cartridge/core and runs `make test`; failures are nonzero, with diagnostic artifacts retained. To enforce it in a hosted repository, enable the workflow and make **Virtual Jaguar E2E / black-screen-regression** a required branch-protection check. Creating the workflow file does not itself change repository protection settings.

The release packer also refuses to package a ROM unless the matrix, full desktop test, both full core paths and structural checks pass for that **exact ROM hash** and the full matrix matches the current test-source hashes. Native-build input hashes must also match; smoke runs alone cannot authorize delivery. A stale report for a different cartridge cannot authorize delivery.

No finite E2E test can guarantee a game will **never** freeze on every emulator, setting, platform or duration. This regression specifically reproduces the old boot defect, tests both boot paths and video standards, continuously watches actual scene pixels/native progress, and proves the detectors reject injected boot, post-boot black and frozen-frame failures. It does **not** resolve the port's performance or remaining feature-parity gaps.
