# Port status — explicit acceptance audit

## Experimental drivable racer; full conversion **INCOMPLETE**

The driving correction makes the native cartridge materially different from the earlier unplayable 68000/software-float build. Real controller input now produces near-real-time movement, braking and heading change, and the Base course has been genuinely finished through its ordered checkpoints. See `PLAYABILITY.md` and the current hash-bound `artifacts/playability-regression/` reports.

This is **not** delivery of full TriggerRally feature parity. The remaining original requirements below have not been removed from scope or treated as an accepted reduction. No dummy editor/profile/network menus are presented as working features.

## Implemented native systems

| Area | Implementation | Qualification |
|---|---|---|
| Cartridge/startup | Freestanding 68000 host, signed GPU/SBL BIOS path, `$83F000` copy bootstrap and genuine `$802000` compatibility entry | Real 4 MiB `.j64`; hardware untested |
| Game execution | Actual C state machine/physics on Jaguar DSP; opposite-bank PCM interrupt mixer | Pinned source-built JRISC tools, project binary32 support and compiler corrections |
| GPU renderer | Actual adapted 42Bastian `jag_3d_engine`: transform, visibility, depth buckets, textured/Gouraud rasterization, blitter and OP lists | Native Q15 rendering/LODs rather than browser shader parity |
| Game states | Course/car menu, countdown, racing, pause, finish, restart and RAM replay | Not the full original website/UI |
| Inputs | Real Jaguar controller matrix, throttle/brake/reverse/handbrake/steering, pause, recovery, camera and restart | Desktop 2.1.3 default A/throttle is **L**, not J |
| Physics | Ported rigid body, engine/power curve/gearbox/clutch/differential, suspension, tyre/chassis/environment sphere contacts, recovery and Icarus wing forces | **50 Hz native fixed step**, binary32 and quantized environment; not original 150-Hz/browser numerical identity |
| Courses/cars | Three shipped checkpoint/start/config records and both vehicle configs | Cropped native terrain/adapted scenery, not the entire original world |
| Geometry/assets | 50 hashed inputs, 8 meshes with full topology retained plus native LODs, 21 CRY textures/material bakes, 14 decoded 8-kHz samples | Converted availability does not mean complete runtime effect/fidelity parity |
| Audio | Real DSP three-voice PCM mixing, engine/skid loops and one-shot events | Original full mixing/effect behavior not complete |
| Timing/progress | Ordered radius-18 checkpoints, finish and session best times | Base finish established by driving; every possible route not established |
| Replay | 2,048 RAM pose/quaternion/frame-interval records and playback | Incomplete replay state and no persistence |
| Performance work | DSP binary32 hot paths; CPU/GPU pipeline; immutable scene/collision caching; fixed-point render-only wheel matrices | Controlled driving checks are low classic-console FPS, not 60 FPS or a worst-case guarantee |
| Regression | Actual desktop application and real stock-clock core; BIOS/video/blitter/reset matrix; specific black/frozen/movement/timing cartridge controls; arithmetic/render units; clean source builds | Finite versions/scenarios, not proof of never freezing |

The older about-0.7-FPS report and ROM `6609ab99…ee78` are historical evidence of the earlier incomplete build, **not current driving approval**. Current reports must match the current ROM and source/core hashes. The release gate refuses stale evidence.

## Remaining requirements — not placeholders or accepted omissions

- **Native track editor:** placement/editing/deletion of checkpoints/scenery, terrain editing, undo/redo and editor camera workflow.
- **Persistent data:** cartridge EEPROM/Memory Track support for tracks, settings, runs, best times and favorites. Present records/best times are volatile RAM only.
- **Profiles/browser metadata/favorites/sharing:** original browser/IndexedDB/account workflows are not converted. No working network bridge, online leaderboard, login or track/run upload/download exists.
- **Full replay/ghost parity:** persistence/browser/export/sharing and full suspension/wheel/engine/flight/audio/camera state capture are missing. Replay's terminal finish state is not a racing course-completion proof.
- **Complete audio/effects:** wind/transmission/all crash variants and source dynamic mixing are not fully wired. Dust/smoke/particles remain incomplete.

## Rendering/content fidelity gaps

1. Terrain is a 128×128, 8-metre-sampled native window with 1/8-metre height quantization and bilinear collision, not the original repeating Catmull–Rom/detail-displaced landscape.
2. All explicitly authored scenery is stored, but extra forest population uses deterministic native candidate placements rather than the original LFIB4 tiled density/gradient generator. Nearest-object and face budgets are native LOD/culling adaptations.
3. CRY, 64×64 textures and Gouraud lighting replace browser shaders. The terrain-vegetation texture is a bake of original shader colours/detail normals, not a tree image used as grass. Alpha-tested vegetation uses real source-data transparency. Dynamic shadows, fog, per-pixel normal maps and full blending differ or remain missing.
4. The Miramar images are converted but the scene background still uses the engine gradient rather than the full skybox.
5. Checkpoints retain the original three double-sided cylinder geometry; native opaque/Gouraud material differs from the original additive/depth-write-disabled effect.
6. Icarus children are in the combined mesh, but faithful articulated wing/control-surface transforms and hierarchy are incomplete. Existing wing physics does not establish visual articulation parity.
7. `/a/meshes/icarus/body.jpg` is absent from the pinned upstream tree. Its original diffuse material colour is retained and the missing reference recorded; no replacement texture is invented.
8. Render matrices/local offsets use native fixed-point precision. Physics orientation remains floating point, but 50-Hz stepping and binary32 arithmetic are numerical adaptations rather than browser identity.

## Coverage and limitations

The driving gate requires all three NTSC courses/both cars, both Base cars under PAL, real-time countdown/acceleration/braking/steering/pause, completed-frame/clock floors, and a true Base/car0 finish in NTSC and PAL. Read its current reports rather than assuming that a changed build passes.

Separate full interaction/safety gates exercise both BIOS paths, real desktop keyboard/window pixels, all menu content, native replay/restart, reset/soak and deliberately broken cartridges. Decoder fixtures are only unit-test inputs; they are not substituted for emulator video.

Dense contacts/scenery/recovery can be slower than controlled free-driving results. Full-course manual driving of every course/car, all flight/collision edge cases, long sessions, every emulator version/setting and physical Jaguar hardware remain unverified. Full feature conversion remains incomplete regardless of a driving-gate pass.

## Content rights

Original code is GPL v3; original content is separately restricted by `licenses/TriggerRally-terms.md`. Miramar attribution permission does not license other content. A buildable experimental cartridge does not create redistribution rights. Obtain necessary permissions before publishing a content-bearing archive or ROM. Build-tool licenses are separate; see `LICENSES.md`.
