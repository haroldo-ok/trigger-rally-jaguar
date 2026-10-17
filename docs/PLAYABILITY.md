# Driving/playability correction

## What the earlier result did not prove

The previously delivered `6609ab99…ee78` cartridge booted and passed bounded black-screen/gameplay interaction checks, but its completed game-frame rate was about 0.7 FPS in the mixed-state run. A 50/60-Hz emulator video callback was not a 50/60-Hz game update. Its 150-Hz simulation on the 68000 software-float runtime could take multiple emulated seconds to produce a new pose. That made holding the accelerator appear ineffective. A boot test was not sufficient acceptance for a playable racer.

The correction is a native architecture/performance change, not a claim that the original port was already playable or that the user merely pressed the wrong key. Virtual Jaguar 2.1.3's default accelerator happens to be keyboard **L** (Jaguar A); keyboard **J** is Jaguar C/handbrake.

## Native execution architecture

- The original signed GPU/SBL path and genuine 68000 `$83F000` copy bootstrap remain. A real 68000 `JMP $83F000` is also present at cartridge `$802000`, providing compatibility with hard-wired-entry frontends and preventing a GPU-only-cart heuristic from silently forcing BIOS on.
- The 68000 host copies the DSP image from **cartridge ROM**, uploads its local code, starts Jerry and sleeps. Source and destination of that copy cannot alias despite their RAM-linked images.
- Jerry runs the actual C state machine, physics and controller scans. Its opposite register bank handles the original three-voice 8-kHz PCM interrupt mixer.
- Tom runs the adapted **42Bastian `jag_3d_engine`**, including terrain/object transforms, face visibility, depth buckets, textured/Gouraud rasterization, blitter use and OP double buffering.
- The DSP submits a complete immutable scene, then calculates the next physical pose while the GPU draws. Course-changing menu actions wait before replacing shared terrain. The next descriptor/camera upload waits for GPU completion.
- Physics uses a **50-Hz native fixed step**, not the source browser's 150-Hz cadence. The existing native force systems remain: rigid body, gearbox/power curve/clutch/differential, suspension, tyre/chassis/scenery contacts, recovery and Icarus wing forces. Binary32, terrain quantization and the changed cadence mean numerical identity to the original browser game is not claimed.
- Immutable scenery matrices and environmental collision-sphere centres/radii are calculated once per course. The collision scene still includes all stored authored instances.
- Render-only car/wheel composition uses native Q15 matrices and Q8-metre local offsets. The order remains `Body * RY(steer) * RX(spin) * RZ(flip)`. Physical body attitude, contacts, wheel state and forces are not replaced by a camera-driving approximation.

No emulator clocks, CPU/GPU/DSP registers or live target RAM are patched by the E2E. The host supplies only controller input and reads native/video/audio output.

## Preferred-source tools and numerical checks

`vendor/jrisc/` contains unchanged, checksum-pinned compiler/assembler/linker source archives. `tools/build_jrisc_tools.py` applies the separate project patch only in the private build cache. This is a source-available/non-commercial vbcc toolchain; consult the original legal terms. No vbcc C runtime is linked into the cartridge.

The project supplies its own GPL binary32 arithmetic. Assembly hot paths use Jerry's integer multiplier/ALU; unusual exponents fall back to the complete local C implementation. Exact integer remainders are reconstructed instead of trusting the DSP remainder latch. Rounding is nearest/ties-to-even; the test treats NaN payload selection as unspecified.

The separate real-DSP unit cartridge checks **10,240 arithmetic operations**, normal/subnormal/zero/infinite/NaN cases, integer conversions, a decrement sequence and **64 render-matrix cases** against read-only host oracles. It is not game E2E evidence and is not distributed as the game. A separate real-68000 arithmetic unit remains as well.

Bring-up found and corrected additional defects in **intermediate new DSP prototypes**, not in the earlier delivered 68000 cartridge:

1. Binary32 GPR argument/result/constant handling and explicit arithmetic lowering in the compiler backend.
2. Local indirect-call pointer fetching and preservation of live aggregate-copy pointers.
3. Reservation of saved temporary registers, preventing a replay-copy loop's data register from aliasing its loop counter.
4. Correct indexed-store dependency recognition in the instruction scheduler.
5. Correct VASM word-indexed audio mailbox/phase accesses. Copying the old assembler's byte-offset spelling verbatim could overwrite arithmetic code; the source now uses the correct indexes.

Failed prototypes and unit/fault cartridges are not packaged as playable game images.

## Playability regression, not just a live counter

Run `make test-driving` or `python3 tests/playability_suite.py`.

Each case uses a fresh stock-clock emulator process and actual cartridge. The suite covers all three courses/both cars in NTSC, plus both Base cars in PAL. It requires:

- A real-time READY countdown, approximately three seconds.
- At least 6 m physical displacement and 4 m/s speed after holding A for 2.5 emulated seconds.
- A race-clock ratio of 0.90–1.10 over that driving window.
- At least 12 completed game FPS for NTSC / 10 for PAL, and no free-driving frame gap beyond 0.30 seconds.
- Multiple distinct live 3D scene images, real ordered checkpoint/replay progress, measurable braking, actual body-heading change under steering and frozen physics/live graphics while paused.
- A genuine Base/car0 finish through both ordered checkpoints in NTSC and PAL. Replay playback is never used to claim course completion.

Specific faulty-cartridge controls keep the renderer/input alive but remove engine power, or insert native racing delay. They must fail the intended movement or real-time/performance assertion; a missing dependency, compiler error or generic emulator crash is not a passing control.

The separate safety matrix still tests BIOS/video/blitter/reset/desktop paths and five specific entry/black/frozen-scene controls. Faster boot/rendering changed fault timing: post-boot controls now allow an observable healthy interval before the fault, then exercise the **same** black/frozen-frame capture watchdogs in an explicit watch mode. Watchdog thresholds are not relaxed to make a fault count as success.

Reports and screenshots live under `artifacts/playability-regression/`; the release gate binds them to the exact ROM, emulator core and current test sources. Controlled driving performance is not a blanket worst-case FPS guarantee.

## Confirmed and unconfirmed scope

The individual stock-core checks recorded Forest/Arbusu displacement **16.9 m / 2.5 s**, **13.6 completed FPS**, and Base/Arbusu **15.4 m / 2.5 s**, **18.4 completed FPS**. The Base route was genuinely finished in about **5.94 s** race time. Actual desktop keyboard/pixel driving is tested separately.

These measurements do not establish every driving path, worst-case collision/recovery/flight performance, long sessions or physical Jaguar behavior. Dense scenery/contact cases can be slower; this is not a 60-FPS game. Full original editor, persistence, profile/network/sharing, replay/ghost and fidelity requirements remain incomplete and have not been removed from scope.
