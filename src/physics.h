/* SPDX-License-Identifier: GPL-3.0-or-later
 * Native translation of Code Artemis game/sim.js and game/vehicle.js.
 * See docs/PORT_STATUS.md for numerical/environment differences.
 */
#ifndef TR_PHYSICS_H
#define TR_PHYSICS_H
#include "math3d.h"
typedef struct { V3 pos,vel,angvel,momentum,force,torque,inertia,inverse;Q4 ori;float matrix[9],mass,damping; } Body;
typedef struct { V3 pos,contactvel;float ride,ridevel,spin,spinvel,frictionx,frictiony; } Wheel;
typedef struct { float throttle,brake,handbrake,turn; } Input;
typedef struct {
    Body body; Wheel wheel[4]; const CarConfig *cfg; const Track *track;
    Input input; float turn,turnvel,shift_timer,total_drive,diff,engine,engine_smoothed,idle,redline,recover_rpm,ratios[10];
    float recover_timer,crash,skid,wing_fold,fold_timer,wing_elevator,wing_rudder,wing_aileron;
    int gear,overspeed,disabled,contact,recovering;V3 recover_pos;Q4 recover_ori;
    unsigned event; /* bit 0 hydraulic, bit 1 slam, bit 2 collision */
} Vehicle;
void vehicle_init(Vehicle *,const CarConfig *,const Track *);
void vehicle_step(Vehicle *,float);
void vehicle_recover(Vehicle *,float);
float terrain_height(const Track *,float,float,V3 *);
#endif
