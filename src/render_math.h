/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef TR_RENDER_MATH_H
#define TR_RENDER_MATH_H
#include <stdint.h>
/* Renderer precision matches the engine's signed Q15 matrices. The physical
   body/tyres retain their floating-point orientation, forces and velocities. */
void render_transform(const int32_t *,const int16_t *,int32_t *);
void render_wheel_matrix(const int32_t *,unsigned,unsigned,int,int32_t *);
void render_z_matrix(unsigned,int32_t *);
#endif
