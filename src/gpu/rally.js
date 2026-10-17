; SPDX-License-Identifier: GPL-3.0-or-later
; Atari Jaguar GPU renderer, adapted from 42Bastian's jag_3d_engine (MIT).
; The 68000 runs the native game; GPU renders only complete submitted scenes.
LYXASS equ 1
    gpu
GOURAUD set 1
SOFTCLIP set 1
LANDSCAPE set 1
TEXTURE set 1
DARKEN set 0
FPS set 1
    include <js/symbols/jagregeq.js>
    include <js/symbols/blit_eq.js>
    include <js/macro/help.mac>
    include <js/macro/module.mac>
    include "globalreg.h"
    include "video.h"
    include "structs.inc"
    include "engine.h"
    include "memory.inc"
    include "../../assets/asset_ids.inc"
_CAMERA_Y equ CAMERA_Y-CAMERA_X
_CAMERA_Z equ CAMERA_Z-CAMERA_X
_CAMERA_ANGLE_Y equ CAMERA_ANGLE_Y-CAMERA_X
_CAMERA_SPEED equ CAMERA_SPEED-CAMERA_X
_LIGHT_X equ LIGHT_X-CAMERA_X
_LIGHT_Y equ LIGHT_Y-CAMERA_X
_LIGHT_Z equ LIGHT_Z-CAMERA_X
_RLIGHT_X equ RLIGHT_X-CAMERA_X
_RLIGHT_Y equ RLIGHT_Y-CAMERA_X
_RLIGHT_Z equ RLIGHT_Z-CAMERA_X
IRQ_STACK equ $f0301c
stacktop equ $f03ffc
    macro WAITBLITTER
.\wait load (blitter+$38),tmp0
    btst #0,tmp0
    jr z,.\wait
    nop
    endm
    macro MyINITMODULE
    movei #(MODrun_\0)+$8000,r0
    movei #MODstart_\0,r1
    movei #1<<16|(MODlen_\0 >> 2),r2
    movei #overlay,r3
    BL (r3)
    endm
    run $2000
start::
    movei #init,r0
    jump (r0)
    nop
    include "irq.js"
    include "engine.js"
    include "plane_prep.js"
    align 8
init:
    movei #$f02100,IRQ_FLAGADDR
    moveta IRQ_FLAGADDR,IRQ_FLAGADDR.a
    movei #1<<14|%11111<<9,r0
    store r0,(IRQ_FLAGADDR)
    nop
    nop
    INITMODULE irq
    movei #IRQ_STACK,IRQ_SP
    moveta IRQ_SP,IRQ_SP.a
    movei #stacktop,SP
    include <js/inc/videoinit.inc>
    movei #$f00028,r0
    movei #VID_MODE,r1
    storew r1,(r0)
    movei #screen0,r1
    moveta r1,screen1.a
    movei #screen1,r1
    moveta r1,screen0.a
    movei #$f14003,r0
    loadb (r0),r0
    movei #obl0,r10
    btst #4,r0
    movei #obl1,r11
    jr eq,pal
    nop
    movei #obl0_60hz,r10
    movei #obl1_60hz,r11
pal:
    move r10,r1
    addq #32,r1
    addq #32,r1
    moveta r1,obl0.a
    addq #32,r11
    addq #32,r11
    moveta r11,obl1.a
    movei #op_list,r1
    moveq #31,r2
.cpyobl:
    load (r10),r3
    addqt #4,r10
    subq #1,r2
    store r3,(r1)
    jr pl,.cpyobl
    addqt #4,r1
    movei #$f00020,r0
    movei #op_list<<16,r1
    store r1,(r0)
    movei #1<<14|%11111<<9|%01000<<4,r1
    store r1,(IRQ_FLAGADDR)
    nop
    nop
    MyINITMODULE planePrep
    MBL planePrep
    moveq #0,r0
    moveta r0,vbl_counter.a
    moveq #1,r0
    moveta r0,VBLFlag.a
    movei #TELEMETRY+4,r1
    moveq #0,r0
    store r0,(r1)
main_loop:
    movei #TELEMETRY+4,r1
.wait_scene:
    load (r1),r0
    cmpq #1,r0
    jr ne,.wait_scene
    nop
    MyINITMODULE engine
    MBL engine
    movei #BLIT_A1_BASE,r14
.wait_blit:
    load (r14+_BLIT_CMD),r0
    btst #0,r0
    jr eq,.wait_blit
    nop
    moveq #0,r0
    moveta r0,VBLFlag.a
.wait_swap:
    movefa VBLFlag.a,r0
    cmpq #0,r0
    jr eq,.wait_swap
    nop
    movei #TELEMETRY+12,r1
    load (r1),r0
    addq #1,r0
    store r0,(r1)
    movei #TELEMETRY+4,r1
    moveq #0,r0
    store r0,(r1)
    movei #main_loop,r0
    jump (r0)
    nop
; Blitter overlay loader from jag_3d_engine. GPU RAM alias avoids bus hazards.
overlay::
    movei #BLIT_A1_BASE,r14
.wbl:
    load (r14+_BLIT_CMD),r3
    shrq #1,r3
    jr cc,.wbl
    nop
    store r0,(r14)
    store r1,(r14+_BLIT_A2_BASE)
    movei #BLIT_PITCH1|BLIT_PIXEL32|BLIT_WID3584|BLIT_XADDPHR,r0
    moveq #0,r1
    store r0,(r14+_BLIT_A1_FLAGS)
    store r0,(r14+_BLIT_A2_FLAGS)
    store r1,(r14+_BLIT_A1_PIXEL)
    store r1,(r14+_BLIT_A2_PIXEL)
    movei #BLIT_SRCEN|BLIT_LFU_REPLACE|BLIT_BUSHI,r1
    store r2,(r14+_BLIT_COUNT)
    store r1,(r14+_BLIT_CMD)
.wbl2:
    shrq #1,r1
    jr cc,.wbl2
    load (r14+_BLIT_CMD),r1
    jump (LR)
    nop
    align 8
obl0: ibytes "obl0_50.bin"
obl1: ibytes "obl1_50.bin"
obl0_60hz: ibytes "obl0_60.bin"
obl1_60hz: ibytes "obl1_60.bin"
    include "sintab.inc"
    align 8
obj_plane:
    dc.w 0,0,0,0,0,0,0,0
    dc.l 0,plane_faces,plane_normals,plane_vnormals
    dc.l plane_rotated,plane_normals_rotated,plane_vnormals_rotated
    dc.l plane_projected,plane_visible
    align 4
dirt_tex_0:
    tex_info_shifted TEX_DIRT, 0,0,63,0,63,63
    tex_info_shifted TEX_DIRT, 0,0,63,63,0,63
grass_tex_0:
    tex_info_shifted TEX_TERRAIN_VEGETATION, 0,0,63,0,63,63
    tex_info_shifted TEX_TERRAIN_VEGETATION, 0,0,63,63,0,63
    align 8
end_gpu::
    echo "GPU code end: %Hend_gpu"
    end
