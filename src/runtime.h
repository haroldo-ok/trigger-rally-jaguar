/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef TR_RUNTIME_H
#define TR_RUNTIME_H
#include "physics.h"
#include "memory.h"
/* Compiler fence/idle instructions for both native CPU backends. */
#ifdef __JRISC__
static void tr_fence(void) = "\tnop\n";
#define TR_FENCE() tr_fence()
#define TR_IDLE() tr_fence()
#else
#define TR_FENCE() __asm__ volatile("":::"memory")
#define TR_IDLE() __asm__ volatile("nop;nop;nop;nop")
#endif
#define REG16(a) (*(volatile uint16_t *)(a))
#define REG32(a) (*(volatile uint32_t *)(a))
#define JOY_A (1u<<29)
#define JOY_PAUSE (1u<<28)
#define JOY_B (1u<<25)
#define JOY_RIGHT (1u<<23)
#define JOY_LEFT (1u<<22)
#define JOY_DOWN (1u<<21)
#define JOY_UP (1u<<20)
#define JOY_1 (1u<<19)
#define JOY_C (1u<<13)
#define JOY_OPTION (1u<<9)
#define JOY_2 (1u<<7)
#define JOY_3 (1u<<3)
#define JOY_0 (1u<<4)
#define JOY_STAR (1u<<16)
#define JOY_HASH 1u
/* Jaguar native fixed-step solver; all source force/contact systems retained.
 * 50 Hz keeps the semi-implicit suspension integration stable while removing
 * redundant 150-Hz browser-era work from Jerry's frame budget. */
#define SIM_HZ 50.f
#define TXT_SCREEN 0x1ff870u
/* Deliberately fixed, documented ABI; tests read emulated RAM, never host state. */
typedef struct {
    volatile uint32_t magic,command,vbl,gpu_frames,cpu_frames,state,track,car,checkpoint,time_ms,speed_q16;
    volatile int32_t x_q16,y_q16,z_q16;
    volatile uint32_t error,input,recorded_frames,flags;
    /* Append-only v1 diagnostics; the original 72-byte ABI stays unchanged. */
    volatile int32_t forward_x_q16,forward_y_q16;
} Telemetry;
#define T ((Telemetry*)ADDR_TELEMETRY)
enum { MENU,COUNTDOWN,RACING,PAUSED,FINISHED,REPLAY };
/* Descriptor's first 52 bytes are the upstream GPU ABI; matrix extends it. */
typedef struct {
    uint16_t visible;int16_t x,y,z;uint16_t dummy,a,b,c;
    const void *points,*faces,*normals,*vnormals;
    void *rotated,*normals_rotated,*vnormals_rotated,*projected,*visible_faces;
    int32_t matrix[9];
    uint32_t scale_q8;
} GPUObject;
void *memcpy(void *,const void *,unsigned long);
void *memset(void *,int,unsigned long);
int strcmp(const char *,const char *);
#endif
