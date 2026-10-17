/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (c) 2012-2013 Code Artemis; native adaptation 2026.
 * Derived from Trigger Rally game/sim.js, game/vehicle.js and game/terrain.js.
 * This is a real force/suspension/powertrain simulation, not a camera driver.
 */
#include "physics.h"
#include "memory.h"
#include <stddef.h>
void *memset(void *,int,size_t);
/* Conservative integer broad phase. This changes no contact equations: it
 * avoids repeating a float-distance scan of the whole world for every clip
 * and wheel at 150 Hz on a 13 MHz CPU. */
typedef struct { int16_t x,y,z,r; } CoarseObject;
static CoarseObject coarse[MAX_SCENERY];
static uint16_t candidates[MAX_SCENERY];
static unsigned candidate_count;
typedef struct { V3 center[3];float radius[3];unsigned count; } CollisionCache;
#define COLLISION_CACHE ((CollisionCache*)ADDR_SCENERY_COLLISION_CACHE)
static const Scenery *prepared_scenery;
static unsigned scenery_spheres(unsigned,V3*,float*);
static int last_cell_x,last_cell_y;
static void prepare_world(const Track*t){
    if(prepared_scenery!=t->scenery){
        for(unsigned i=0;i<t->scenery_count&&i<MAX_SCENERY;i++){
            const Scenery*s=t->scenery+i;coarse[i]=(CoarseObject){(int)s->pos.x,(int)s->pos.y,(int)s->pos.z,(int)(12*s->scale)+3};
            CollisionCache*d=COLLISION_CACHE+i;V3 a[3];float r[3],mat[9];
            d->count=scenery_spheres(s->layer,a,r);
            Q4 q=qm(qm(qaxis(v3(0,0,1),s->rot.z),qaxis(v3(0,1,0),s->rot.y)),qaxis(v3(1,0,0),s->rot.x));qmatrix(q,mat);
            for(unsigned j=0;j<d->count;j++){d->center[j]=add(s->pos,mv(mat,mul(a[j],s->scale)));d->radius[j]=r[j]*s->scale;}
        }
        prepared_scenery=t->scenery;
    }
    last_cell_x=last_cell_y=0x7fffffff;candidate_count=0;
}
static void refresh_candidates(Vehicle*v){
    int x=(int)v->body.pos.x,y=(int)v->body.pos.y,cx=x>>3,cy=y>>3;
    if(cx==last_cell_x&&cy==last_cell_y)return;
    last_cell_x=cx;last_cell_y=cy;candidate_count=0;
    for(unsigned i=0;i<v->track->scenery_count&&i<MAX_SCENERY;i++){
        CoarseObject*c=coarse+i;int r=c->r+32,dx=x-c->x,dy=y-c->y;
        if(dx>=-r&&dx<=r&&dy>=-r&&dy<=r)candidates[candidate_count++]=i;
    }
}
static V3 locpoint(Body*b,V3 p){return add(b->pos,mv(b->matrix,p));}
static V3 pointvel(Body*b,V3 p){return add(b->vel,cross(b->angvel,sub(p,b->pos)));}
static void force_at(Body*b,V3 f,V3 p){b->force=add(b->force,f);b->torque=add(b->torque,cross(sub(p,b->pos),f));}
static void local_force(Body*b,V3 f){b->force=add(b->force,mv(b->matrix,f));}
static void local_torque(Body*b,V3 t){b->torque=add(b->torque,mv(b->matrix,t));}
static void inertia(Body*b,V3 dimensions){
    V3 r=mul(dimensions,.5f);float s=b->mass*.5f;
    b->inertia=v3((r.y*r.y+r.z*r.z)*s,(r.z*r.z+r.x*r.x)*s,(r.x*r.x+r.y*r.y)*s);
    b->inverse=v3(1/b->inertia.x,1/b->inertia.y,1/b->inertia.z);
}
float terrain_height(const Track*t,float x,float y,V3*normal){
    float tx=clampf((x-t->origin_x)/MAP_STEP,0,MAP_N-1.001f),ty=clampf((y-t->origin_y)/MAP_STEP,0,MAP_N-1.001f);
    int ix=(int)tx,iy=(int)ty;float u=tx-ix,v=ty-iy;
    const int16_t*h=t->height+iy*MAP_N+ix;
    float a=h[0]/8.f,b=h[1]/8.f,c=h[MAP_N]/8.f,d=h[MAP_N+1]/8.f;
    if(normal)*normal=normalized(v3(-lerpf(b-a,d-c,v)/MAP_STEP,-lerpf(c-a,d-b,u)/MAP_STEP,1));
    return lerpf(lerpf(a,b,u),lerpf(c,d,u),v);
}
static float power(const CarConfig*c,float rpm){
    const PowerPoint*p=c->power;float a=rpm*60/TAU;
    if(a<=0)return 0;if(a<=p[0].rpm)return p[0].power*a/p[0].rpm;
    for(unsigned i=1;i<c->power_count;i++)if(a<=p[i].rpm)return lerpf(p[i-1].power,p[i].power,(a-p[i-1].rpm)/(p[i].rpm-p[i-1].rpm));
    return p[c->power_count-1].power;
}
void vehicle_init(Vehicle*v,const CarConfig*c,const Track*t){
    memset(v,0,sizeof(*v));v->cfg=c;v->track=t;v->body.mass=c->mass;v->body.pos=t->start;prepare_world(t);
    Q4 base={.5f,.5f,.5f,.5f};v->body.ori=qm(qaxis(v3(0,0,1),t->heading),base);
    qmatrix(v->body.ori,v->body.matrix);inertia(&v->body,c->dimensions);v->body.damping=1e-10f;
    v->turn=-1;v->gear=1;v->wing_fold=1;
    for(unsigned i=0;i<c->wheel_count;i++){v->wheel[i].pos=sub(c->wheels[i].pos,c->center);v->total_drive+=c->wheels[i].drive;}
    v->idle=c->power[0].rpm*TAU/60;v->engine=v->idle;v->redline=c->redline*TAU/60;v->recover_rpm=.98f*v->redline;
    v->ratios[0]=-c->reverse*c->final;v->ratios[1]=0;for(unsigned i=0;i<c->gear_count;i++)v->ratios[i+2]=c->gears[i]*c->final;
}
static float torque_in(Vehicle*v,int gear){
    float speed=v->engine*v->ratios[gear+1]/v->ratios[v->gear+1];
    return speed>1e-6f?power(v->cfg,speed)*v->ratios[gear+1]/speed:0;
}
void vehicle_recover(Vehicle*v,float dt){
    Body*b=&v->body;
    if(!v->recovering){
        float a=atan2f_local(b->matrix[2],b->matrix[0]);
        Q4 q={.70710678f,0,0,.70710678f};v->recover_ori=qm(q,qaxis(v3(0,1,0),PI-a));
        float d=b->ori.x*v->recover_ori.x+b->ori.y*v->recover_ori.y+b->ori.z*v->recover_ori.z+b->ori.w*v->recover_ori.w;
        if(d<0){v->recover_ori.x=-v->recover_ori.x;v->recover_ori.y=-v->recover_ori.y;v->recover_ori.z=-v->recover_ori.z;v->recover_ori.w=-v->recover_ori.w;}
        v->recover_pos=add(b->pos,v3(0,0,4));v->recovering=1;v->disabled=1;
    }
    b->pos=add(b->pos,mul(sub(v->recover_pos,b->pos),minf(dt*4,1)));
    b->ori.x=pull(b->ori.x,v->recover_ori.x,dt*4);b->ori.y=pull(b->ori.y,v->recover_ori.y,dt*4);b->ori.z=pull(b->ori.z,v->recover_ori.z,dt*4);b->ori.w=pull(b->ori.w,v->recover_ori.w,dt*4);
    b->ori=qnorm(b->ori);qmatrix(b->ori,b->matrix);b->vel=b->angvel=b->momentum=v3(0,0,0);
    if(v->recover_timer>=v->cfg->recover_release){v->recover_timer=0;v->recovering=0;v->disabled=0;}
}
/* Contact basis and response follow the original damped spring/friction model. */
static void basis(V3 n,V3 right,V3*u,V3*vv){*vv=normalized(cross(n,right));*u=normalized(cross(*vv,n));}
static void chassis_contact(Vehicle*v,V3 p,V3 normal,float depth){
    Body*b=&v->body;V3 u,w;basis(normal,v3(1,0,0),&u,&w);V3 vel=pointvel(b,p);
    float x=dot(vel,u),y=dot(vel,w),z=dot(vel,normal),perp=depth*200000-z*8000;
    if(perp<=0)return;
    float fx=-x*10000,fy=-y*10000,l=sqrtf_local(fx*fx+fy*fy),max=perp*.81f;
    v->skid+=clampf(l/max-.75f,0,1)*perp;
    if(l>perp*1.08f){float s=max/l;fx*=s;fy*=s;}
    force_at(b,add(mul(normal,perp),add(mul(u,fx),mul(w,fy))),p);v->crash=maxf(v->crash,perp);v->contact=1;
}
/* Upstream environment collision sphere definitions, transformed per instance. */
static unsigned scenery_spheres(unsigned layer,V3*p,float*r){
    switch(layer){
    case 1:p[0]=v3(9,0,1);p[1]=v3(-9,0,1);r[0]=r[1]=2;return 2;
    case 2:p[0]=v3(0,0,.5f);p[1]=v3(0,0,1.5f);r[0]=r[1]=1;return 2;
    case 3:p[0]=v3(0,-.9f,.5f);p[1]=v3(0,.9f,.5f);r[0]=r[1]=1;return 2;
    case 4:p[0]=v3(0,0,.25f);p[1]=v3(0,0,.75f);p[2]=v3(0,0,1.75f);r[0]=r[1]=.5f;r[2]=1;return 3;
    default:return 0;
    }
}
/* Narrow phase considers all authored instances, but rejects distant ones first.
 * Wheel contacts are handled through the same full 3D sphere test as chassis. */
typedef void (*ContactFn)(Vehicle*,void*,V3,V3,float);
static void static_contacts(Vehicle*v,V3 p,float radius,ContactFn fn,void*ctx){
    const Track*t=v->track;
    if(!candidate_count)return;
    int px=(int)p.x,py=(int)p.y,pz=(int)p.z;
    for(unsigned k=0;k<candidate_count;k++){
        unsigned i=candidates[k];CoarseObject*co=coarse+i;int r0=co->r+3,dx=px-co->x,dy=py-co->y,dz=pz-co->z;
        if(dx>r0||dx< -r0||dy>r0||dy< -r0||dz>r0||dz< -r0)continue;
        const Scenery*s=t->scenery+i;V3 d=sub(p,s->pos);float reach=radius+12*s->scale;
        if(absf(d.x)>reach||absf(d.y)>reach||absf(d.z)>reach)continue;
        const CollisionCache*cached=COLLISION_CACHE+i;
        for(unsigned j=0;j<cached->count;j++){
            V3 center=cached->center[j],delta=sub(p,center);float dist2=dot(delta,delta),sum=radius+cached->radius[j];
            if(dist2<sum*sum){float dist=sqrtf_local(dist2);V3 normal=dist>.001f?mul(delta,1/dist):v3(1,0,0);fn(v,ctx,add(center,mul(normal,cached->radius[j])),normal,sum-dist);}
        }
    }
}
static void chassis_callback(Vehicle*v,void*ctx,V3 p,V3 n,float depth){(void)ctx;chassis_contact(v,p,n,depth);}
typedef struct { Wheel*w;const WheelConfig*c;V3 right,clip; } WheelContact;
static void wheel_contact(Vehicle*v,void*ctx,V3 p,V3 n,float depth){
    WheelContact*wc=ctx;Wheel*w=wc->w;Body*b=&v->body;V3 u,vv;basis(n,wc->right,&u,&vv);
    V3 velocity=pointvel(b,p);float x=dot(velocity,u),y=dot(velocity,vv)+w->spinvel*wc->c->radius,z=dot(velocity,n);
    w->contactvel=add(velocity,mul(vv,w->spinvel*wc->c->radius));v->contact=1;
    float suspdot=dot(n,v3(b->matrix[1],b->matrix[4],b->matrix[7]));w->ride+=suspdot*depth;
    float perp;
    if(w->ride>.14f){float over=w->ride-.14f;w->ride=.14f;w->ridevel=0;perp=.14f*120000+over*200000-z*8000;}
    else{w->ride=maxf(w->ride,-.14f);w->ridevel=maxf(w->ridevel,-z);perp=w->ride*120000+w->ridevel*20000;}
    float side=1-suspdot*suspdot;perp=perp*suspdot+(depth*200000-z*8000)*side;
    if(perp<=0)return;
    float fx=-x*3000,fy=-y*3000,l=sqrtf_local(fx*fx+fy*fy),max=perp*1.08f;
    v->skid+=clampf(l/max-.75f,0,1)*perp;
    if(l>perp*1.44f){float s=max/l;fx*=s;fy*=s;}
    w->frictionx+=fx;w->frictiony+=fy;force_at(b,add(mul(n,perp),add(mul(u,fx),mul(vv,fy))),wc->clip);
    v->crash=maxf(v->crash,perp*side);
}
static void tick_wheel(Vehicle*v,unsigned i,float dt){
    Wheel*w=v->wheel+i;const WheelConfig*c=v->cfg->wheels+i;Body*b=&v->body;
    float suspension=w->ride*120000;w->frictionx=w->frictiony=0;
    w->ridevel-=suspension/15*dt;w->ridevel/=1+100*dt;w->ride+=w->ridevel*dt;
    w->spin+=w->spinvel*dt;while(w->spin>TAU)w->spin-=TAU;while(w->spin<0)w->spin+=TAU;
    V3 p=w->pos;p.y+=w->ride;p=locpoint(b,p);
    float turn=c->turn*v->turn,cs=cosf_local(turn),sn=sinf_local(turn);
    V3 right=v3(b->matrix[0]*cs-b->matrix[2]*sn,b->matrix[3]*cs-b->matrix[5]*sn,b->matrix[6]*cs-b->matrix[8]*sn);
    WheelContact ctx={w,c,right,p};static_contacts(v,p,c->radius,wheel_contact,&ctx);
    V3 down=cross(right,cross(right,v3(0,0,1)));V3 clip=add(p,mul(down,c->radius));ctx.clip=clip;
    V3 normal;float h=terrain_height(v->track,clip.x,clip.y,&normal),depth=(h-clip.z)*normal.z;
    if(depth>0)wheel_contact(v,&ctx,clip,normal,depth);
}
static void body_step(Body*b,float dt){
    V3 acc=add(mul(b->force,1/b->mass),v3(0,0,-9.81f));b->vel=add(b->vel,mul(acc,dt));b->pos=add(b->pos,mul(b->vel,dt));
    b->momentum=add(b->momentum,mul(b->torque,dt));b->momentum=mul(b->momentum,1/(1+dot(b->momentum,b->momentum)*dt*b->damping));
    V3 a=mtv(b->matrix,b->momentum);a.x*=b->inverse.x;a.y*=b->inverse.y;a.z*=b->inverse.z;b->angvel=mv(b->matrix,a);
    Q4 omega={b->angvel.x*dt*.5f,b->angvel.y*dt*.5f,b->angvel.z*dt*.5f,0};Q4 spin=qm(omega,b->ori);
    b->ori.x+=spin.x;b->ori.y+=spin.y;b->ori.z+=spin.z;b->ori.w+=spin.w;b->ori=qnorm(b->ori);qmatrix(b->ori,b->matrix);
    b->force=b->torque=v3(0,0,0);
}
static void wing_step(Vehicle*v,float dt){
    Body*b=&v->body;int fold=1;
    if(v->contact){if(v->fold_timer>=.5f)v->event|=1;v->fold_timer=0;}
    else{v->fold_timer+=dt;if(v->fold_timer>=.5f)fold=0;}
    float old=v->wing_fold;v->wing_fold=toward(old,fold?1:0,dt*3);
    if((old==1&&v->wing_fold<1)||(old==0&&v->wing_fold>0))v->event|=1;
    if((v->wing_fold==1&&old<1)||(v->wing_fold==0&&old>0))v->event|=2;
    float factor=1-v->wing_fold;
    if(factor==0){
        if(old<1){inertia(b,v->cfg->dimensions);b->damping=1e-10f;}
        return; /* Folded wings exert exactly zero aerodynamic force. */
    }
    inertia(b,v->cfg->dimensions);float guess=b->inertia.x;
    b->inertia=v3(lerpf(b->inertia.x,guess,factor),lerpf(b->inertia.y,guess*2,factor),lerpf(b->inertia.z,guess,factor));
    /* Original wing inverse inertia has a deliberate asymmetric Y factor. */
    b->inverse=v3(lerpf(b->inverse.x,1/guess,factor),lerpf(b->inverse.y,2/guess,factor),lerpf(b->inverse.z,1/guess,factor));
    b->damping=1e-10f*(1+30.6228f*factor);
    V3 lv=mtv(b->matrix,b->vel),av=mtv(b->matrix,b->angvel);float logvel=logf_local(absf(lv.z)+.5f);
    float pitch=acosf_local(b->matrix[8]),roll=asinf_local(b->matrix[6]);
    float x=clampf(.05f+PI/2-pitch+(v->input.throttle-v->input.brake)*.6f,-1,1),y=clampf(v->turn*.8f,-1,1),z=clampf(v->turn*.2f-roll,-1,1);
    v->wing_elevator=x;v->wing_rudder=y;v->wing_aileron=z;
    V3 target=mul(v3(x,y,z),2);local_torque(b,mul(target,30*factor));local_torque(b,mul(sub(target,av),logvel*1500*factor));
    local_torque(b,v3(-lv.y*300*factor-lv.z*30*factor,lv.x*300*factor,0));
    local_force(b,v3(-(10+150*logvel)*factor*lv.x*absf(lv.x),-(10+150*logvel)*factor*lv.y*absf(lv.y),-.3f*factor*lv.z*absf(lv.z)));
}
void vehicle_step(Vehicle*v,float dt){
    Body*b=&v->body;const CarConfig*c=v->cfg;
    /* Original Sim integrates RigidBody before Vehicle, accumulating next forces. */
    body_step(b,dt);refresh_candidates(v);
    float throttle=v->input.throttle,brake=v->input.brake,hand=v->input.handbrake,desired=v->input.turn;
    if(v->shift_timer<=0){
        float torque=power(c,v->engine)*v->ratios[v->gear+1]/maxf(v->engine,1);
        if(v->gear>=1){
            if(v->gear>1&&torque_in(v,v->gear-1)>torque){v->gear--;v->shift_timer=.2f;}
            else if(v->gear<(int)c->gear_count&&torque_in(v,v->gear+1)>torque){v->gear++;v->shift_timer=.2f;}
            else if(brake>.1f&&v->diff<1){v->gear=-1;throttle=brake;brake=0;v->shift_timer=.2f;}
        }else if(v->gear==-1){if(throttle>.1f){v->gear=1;v->shift_timer=.2f;}else{throttle=brake;brake=0;}}
    }else v->shift_timer-=dt;
    int clutch=!(hand>=.5f&&!c->wings);
    if(v->disabled){clutch=0;brake=1;desired=0;}
    v->crash=pull(v->crash,0,dt*5);v->skid=0;
    if((v->contact&&b->matrix[7]<=.1f)||v->recover_timer>=c->recover_trigger){v->recover_timer+=dt;if(v->recover_timer>=c->recover_trigger)vehicle_recover(v,dt);}else v->recover_timer=0;
    float diff=0,lateral=0;
    for(unsigned i=0;i<c->wheel_count;i++){diff+=v->wheel[i].spinvel*c->wheels[i].drive;lateral+=v->wheel[i].frictionx*c->wheels[i].turn;}
    diff/=v->total_drive;v->diff=diff;float ratio=v->ratios[v->gear+1];
    if(ratio!=0&&clutch)v->engine=diff*ratio;v->engine=maxf(v->engine,v->idle);
    if(v->overspeed){v->overspeed=v->engine>v->recover_rpm;if(v->overspeed)throttle=0;}
    else if(v->engine>v->redline){throttle=0;v->overspeed=1;}
    float extended=(throttle-.5f)*2;
    float engine_torque=extended>=0?extended*c->powerscale*1000*power(c,v->engine)/v->engine:.1f*extended*(v->engine-v->idle);
    float perwheel=0;
    if(ratio!=0&&clutch)perwheel=engine_torque*ratio/v->total_drive;
    else v->engine=maxf(v->idle,v->engine+50000*engine_torque*dt/c->flywheel);
    if(c->wings)wing_step(v,dt);v->contact=0;
    for(unsigned i=0;i<c->wheel_count;i++){
        Wheel*w=v->wheel+i;const WheelConfig*wc=c->wheels+i;float wt=w->frictiony*.3f;
        if(wc->drive)wt+=(perwheel-(w->spinvel-diff)*400)*wc->drive;
        w->spinvel+=2*wt/15/wc->radius*.3f*dt;
        float braking=brake*wc->brake+hand*wc->handbrake;if(braking>0)w->spinvel=toward(w->spinvel,0,braking*dt);
    }
    for(unsigned i=0;i<c->clip_count;i++){
        V3 p=locpoint(b,sub(c->clips[i].pos,c->center));V3 normal;V3 bottom=p;bottom.z-=c->clips[i].radius;
        float h=terrain_height(v->track,bottom.x,bottom.y,0);
        if(h>bottom.z){terrain_height(v->track,bottom.x,bottom.y,&normal);chassis_contact(v,bottom,normal,(h-bottom.z)*normal.z);}
        static_contacts(v,p,c->clips[i].radius,chassis_callback,0);
    }
    float tv=clampf((desired-v->turn)*400-v->turnvel*20-lateral*.025f,-8,8);
    v->turnvel=pull(v->turnvel,tv,dt*10);v->turn=clampf(v->turn+v->turnvel*dt,-1,1);
    for(unsigned i=0;i<c->wheel_count;i++)tick_wheel(v,i,dt);
    v->engine_smoothed=pull(v->engine_smoothed,v->engine,dt*100000/c->flywheel);
    if(v->crash>40000)v->event|=4;
}
