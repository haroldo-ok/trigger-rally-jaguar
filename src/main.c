/* SPDX-License-Identifier: GPL-3.0-or-later
 * Native Atari Jaguar runtime. No JS, browser, host rendering or mocked input.
 */
#include "runtime.h"
#include "render_math.h"
#include "../assets/asset_ids.h"
extern const unsigned char gpu_blob[],gpu_blob_end[],audio_blob[],audio_blob_end[],font_blob[];
static Vehicle vehicle;
static Track track;
static unsigned track_id,car_id,state=MENU,previous_state,next_cp,camera_mode;
static float race_time,accumulator,last_cp_distance,countdown;
static unsigned last_joy,last_vbl,loaded_track=0xffffffffu;
static float best[3][2];
#define REPLAY_CAP 2048
typedef struct { V3 pos;Q4 ori;float dt; } ReplayFrame;
#define recording ((ReplayFrame*)ADDR_REPLAY_FRAMES)
static unsigned recorded,replay_cursor;static float replay_accum;
static V3 camera;static float camera_heading;
static uint32_t arena,object_count,face_budget;
static unsigned audio_event_generation;
static int16_t render_wheel_pos[4][3],render_center[3];

static const Sample *engine_sound,*skid_sound;
typedef struct { const Mesh *mesh;GPUObject proto; } CachedScene;
#define SCENERY_CACHE ((CachedScene*)ADDR_SCENERY_DRAW_CACHE)
static void prepare_scenery_scene(void){
    /* Authored scenery is immutable: its world matrix never needs to be
       recalculated every rendered frame. All instances remain in collision. */
    for(unsigned k=0;k<track.scenery_count;k++){
        const Scenery*s=track.scenery+k;CachedScene*d=SCENERY_CACHE+k;
        d->mesh=ASSETS->meshes+s->mesh;GPUObject*o=&d->proto;
        o->x=(int16_t)((s->pos.x-track.origin_x)*8);o->y=(int16_t)(s->pos.z*8);o->z=(int16_t)((s->pos.y-track.origin_y)*8);
        float matrix[9];Q4 q=qm(qm(qaxis(v3(0,0,1),s->rot.z),qaxis(v3(0,1,0),s->rot.y)),qaxis(v3(1,0,0),s->rot.x));qmatrix(q,matrix);
        for(unsigned i=0;i<9;i++){unsigned row=i/3,col=i%3,source_row=row==1?2:row==2?1:0;o->matrix[i]=(int32_t)(matrix[source_row*3+col]*32767);}
        o->scale_q8=(uint32_t)(s->scale*256);
    }
}

void *memcpy(void*d,const void*s,unsigned long n){unsigned char*a=d;const unsigned char*b=s;while(n--)*a++=*b++;return d;}
void *memset(void*d,int v,unsigned long n){
    unsigned char*a=d;while(n&&((uint32_t)a&3)){*a++=(unsigned char)v;n--;}
    uint32_t word=(unsigned char)v;word|=word<<8;word|=word<<16;
    uint32_t*p=(uint32_t*)a;while(n>=16){p[0]=p[1]=p[2]=p[3]=word;p+=4;n-=16;}
    while(n>=4){*p++=word;n-=4;}a=(unsigned char*)p;while(n--)*a++=(unsigned char)v;return d;
}
int strcmp(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return (unsigned char)*a-(unsigned char)*b;}
static void copy_longs(void*d,const void*s,unsigned long n){uint32_t*a=d;const uint32_t*b=s;for(unsigned long i=0;i<n/4;i++)a[i]=b[i];}
static uint32_t ror(uint32_t a,unsigned n){return (a>>n)|(a<<(32-n));}
static unsigned joy_read(void){
    unsigned mask=0xf0fffffcu,j=0xffffffffu;
    REG16(0xf14000)=0x81fe;j&=ror(REG32(0xf14000)|mask,4);
    REG16(0xf14000)=0x81fd;j&=ror(REG32(0xf14000)|mask,8);
    REG16(0xf14000)=0x81fb;j&=ror(REG32(0xf14000)|mask,20);
    REG16(0xf14000)=0x81f7;j&=ror(REG32(0xf14000)|mask,24);
    REG16(0xf14000)=0x8170;return ~j;
}
static void txt(unsigned row,unsigned col,const char*s){
    volatile uint8_t*dst=(uint8_t*)TXT_SCREEN;
    for(;*s&&col<48;s++,col++)for(unsigned y=0;y<8;y++)dst[(row*8+y)*48+col]=font_blob[8+(unsigned char)*s*8+y];
}
static void number(unsigned row,unsigned col,unsigned value,unsigned width){
    char b[12];if(width>10)width=10;b[width]=0;for(unsigned i=width;i;i--){b[i-1]='0'+value%10;value/=10;}txt(row,col,b);
}
static const Sample*sound(const char*name){for(unsigned i=0;i<ASSETS->sample_count;i++)if(!strcmp(ASSETS->samples[i].name,name))return ASSETS->samples+i;return 0;}
static void play(unsigned channel,const Sample*s,unsigned gain,unsigned step,unsigned loop){
    if(!s||channel>2)return;volatile uint32_t*p=(uint32_t*)(0x1800+32*channel);
    unsigned gen=p[0]+2;p[0]=gen|1;TR_FENCE();
    p[1]=(uint32_t)s->pcm;p[2]=s->length;p[3]=0;p[4]=step;p[5]=gain;p[6]=loop;
    TR_FENCE();p[0]=gen&~1u;
}
static void sfx(const char*name,unsigned gain){play(2,sound(name),gain,256,0);audio_event_generation++;}
static void audio_update(void){
    volatile uint32_t*e=(uint32_t*)0x1800,*s=(uint32_t*)0x1820;
    float rpm=vehicle.engine_smoothed*60/TAU;
    e[4]=(unsigned)clampf(rpm/7500*256,50,440);e[5]=(state==RACING||state==COUNTDOWN)?(unsigned)(22+vehicle.input.throttle*35):8;
    s[5]=state==RACING?(unsigned)clampf(vehicle.skid/1500,0,26):0;
    if(vehicle.event&4)sfx("crash1",45);else if(vehicle.event&2)sfx("slam",50);else if(vehicle.event&1)sfx("hydraulic",45);vehicle.event=0;
}
static void load_track(void){
    track=ASSETS->tracks[track_id];
    if(loaded_track!=track_id){
        copy_longs((void*)ADDR_plane_y,track.height,MAP_N*MAP_N*2);
        copy_longs((void*)ADDR_plane_col,track.color,MAP_N*MAP_N*2);
        copy_longs((void*)ADDR_plane_normals,track.normals,MAP_N*MAP_N*16);
        copy_longs((void*)ADDR_plane_vnormals,track.vnormals,MAP_N*MAP_N*8);
        prepare_scenery_scene();loaded_track=track_id;
    }
    /* Collision samples the SAME quantized heightfield used by the GPU. */
    track.height=(const int16_t*)ADDR_plane_y;
    vehicle_init(&vehicle,ASSETS->cars+car_id,&track);
    for(unsigned j=0;j<3;j++)render_center[j]=(int16_t)(((const float*)&vehicle.cfg->center)[j]*256);
    for(unsigned i=0;i<vehicle.cfg->wheel_count;i++)for(unsigned j=0;j<3;j++)render_wheel_pos[i][j]=(int16_t)(((const float*)&vehicle.wheel[i].pos)[j]*256);
    next_cp=0;race_time=0;countdown=3;accumulator=0;last_cp_distance=-1;
    camera=add(vehicle.body.pos,v3(0,0,3));camera_heading=track.heading;
}
static void restart(void){load_track();recorded=0;state=COUNTDOWN;sfx("voice",45);}
static void *alloc(unsigned n){n=(n+7)&~7u;if(arena+n>ADDR_SCRATCH_END){T->error=2;return 0;}void*p=(void*)arena;arena+=n;return p;}
static GPUObject *begin_object(const Mesh*m){
    if(object_count>=MAX_SCENE_OBJECTS||face_budget+m->triangles>3600)return 0;
    unsigned size=m->vertices*24+m->triangles*12+24;
    if(arena+size+48>ADDR_SCRATCH_END){T->error=2;return 0;}
    GPUObject*o=(GPUObject*)ADDR_SCENE_OBJECTS+object_count;
    o->visible=0;o->dummy=o->a=o->b=o->c=0;
    o->points=m->points;o->faces=m->faces;o->normals=m->normals;o->vnormals=m->vnormals;
    o->rotated=alloc(4+m->vertices*8);o->normals_rotated=alloc(4+m->triangles*8);o->vnormals_rotated=alloc(4+m->vertices*8);o->projected=alloc(4+m->vertices*8);o->visible_faces=alloc(4+m->triangles*4);
    ((uint32_t*)ADDR_OBJECT_LIST)[object_count++]=(uint32_t)o;((uint32_t*)ADDR_OBJECT_LIST)[object_count]=0;face_budget+=m->triangles;
    return o;
}
static void object(const Mesh*m,V3 pos,const float*matrix,float scale){
    GPUObject*o=begin_object(m);if(!o)return;
    o->x=(int16_t)((pos.x-track.origin_x)*8);o->y=(int16_t)(pos.z*8);o->z=(int16_t)((pos.y-track.origin_y)*8);
    /* Source: X/Y ground, Z up; engine: X/Z ground, Y up. */
    for(unsigned i=0;i<9;i++){unsigned row=i/3,col=i%3,source_row=row==1?2:row==2?1:0;o->matrix[i]=(int32_t)(matrix[source_row*3+col]*32767);}
    o->scale_q8=(uint32_t)(scale*256);
}
static void object_q15(const Mesh*m,const int32_t*p,const int32_t*matrix){
    GPUObject*o=begin_object(m);if(!o)return;
    o->x=p[0]>>5;o->y=p[2]>>5;o->z=p[1]>>5;o->scale_q8=256;
    for(unsigned i=0;i<9;i++){unsigned row=i/3,col=i%3,source_row=row==1?2:row==2?1:0;o->matrix[i]=matrix[source_row*3+col];}
}
static void cached_object(const CachedScene*c){
    GPUObject*o=begin_object(c->mesh);if(!o)return;
    o->x=c->proto.x;o->y=c->proto.y;o->z=c->proto.z;
    for(unsigned j=0;j<9;j++)o->matrix[j]=c->proto.matrix[j];o->scale_q8=c->proto.scale_q8;
}
static void build_scene(float dt){
    const CarConfig*c=vehicle.cfg;Body*b=&vehicle.body;arena=ADDR_OBJECT_SCRATCH;object_count=0;face_budget=0;
    const Mesh*meshes=ASSETS->meshes;
    /* Physics supplies its full body attitude. Compose render-only wheel
       spin/steering with the engine's native Q15 ALU, not software quaternions. */
    int32_t bm[9],base[3],center[3],pos[3];
    for(unsigned j=0;j<9;j++)bm[j]=(int32_t)(b->matrix[j]*32767);
    base[0]=(int32_t)((b->pos.x-track.origin_x)*256);base[1]=(int32_t)((b->pos.y-track.origin_y)*256);base[2]=(int32_t)(b->pos.z*256);
    render_transform(bm,render_center,center);
    for(unsigned j=0;j<3;j++)pos[j]=base[j]-center[j];
    object_q15(meshes+c->body_mesh,pos,bm);
    for(unsigned i=0;i<c->wheel_count;i++){
        Wheel*w=vehicle.wheel+i;const WheelConfig*wc=c->wheels+i;
        int16_t local[3]={render_wheel_pos[i][0],render_wheel_pos[i][1]+(int)(w->ride*256),render_wheel_pos[i][2]};
        int32_t wm[9],offset[3];render_transform(bm,local,offset);
        for(unsigned j=0;j<3;j++)pos[j]=base[j]+offset[j];
        int turn=(int)(wc->turn*vehicle.turn*(512/TAU)),spin=(int)(w->spin*(512/TAU));
        render_wheel_matrix(bm,turn,spin,wc->flip,wm);object_q15(meshes+c->wheel_mesh,pos,wm);
    }
    /* Closest-first selection bounds both GPU work and scratch memory. All
     * authored objects remain in the collision scene and cartridge data. */
    unsigned picked[24],count=0;uint32_t dist[24];
    /* Cull/sort in the very same eighth-metre coordinates sent to the GPU.
       Only visual selection is quantized; physics still tests every author-
       supplied instance against its original full-precision collision data. */
    int cx=(int)((b->pos.x-track.origin_x)*8),cy=(int)((b->pos.y-track.origin_y)*8);
    for(unsigned i=0;i<track.scenery_count;i++){
        const CachedScene*c=SCENERY_CACHE+i;int dx=c->proto.x-cx,dy=c->proto.z-cy;
        if(dx>760||dx< -760||dy>760||dy< -760)continue;
        uint32_t dd=dx*dx+dy*dy;if(dd>760*760)continue;
        unsigned k=count;while(k&&dd<dist[k-1])k--;
        if(k>=24)continue;unsigned end=count<24?count++:23;
        for(unsigned j=end;j>k;j--){picked[j]=picked[j-1];dist[j]=dist[j-1];}picked[k]=i;dist[k]=dd;
    }
    for(unsigned k=0;k<count;k++)cached_object(SCENERY_CACHE+picked[k]);
#ifdef MESH_CHECKPOINT
    if(next_cp<track.cp_count){
        const V3*p=&track.cp[next_cp].pos;int32_t mat[9],pos[3]={(int32_t)((p->x-track.origin_x)*256),(int32_t)((p->y-track.origin_y)*256),(int32_t)((p->z+2)*256)};
        render_z_matrix((int)(race_time*(.7f*512/TAU)),mat);object_q15(meshes+MESH_CHECKPOINT,pos,mat);
    }
#endif
    float desired=atan2f_local(b->matrix[5],b->matrix[2]);float delta=desired-camera_heading;
    while(delta>PI)delta-=TAU;while(delta< -PI)delta+=TAU;camera_heading+=delta*minf(dt*5,1);
    float distance=camera_mode?13:7.5f,cs=cosf_local(camera_heading),sn=sinf_local(camera_heading);
    V3 target=add(b->pos,v3(-cs*distance,-sn*distance,camera_mode?5.5f:2.8f));
    target.z=maxf(target.z,terrain_height(&track,target.x,target.y,0)+1.3f);
    if(state==MENU){target=add(b->pos,v3(-cs*8,-sn*8,3));camera=target;}else camera=add(camera,mul(sub(target,camera),minf(1,dt*8)));
    REG32(ADDR_CAMERA_X)=(int32_t)((camera.x-track.origin_x)*8);REG32(ADDR_CAMERA_Y)=(int32_t)(camera.z*8);REG32(ADDR_CAMERA_Z)=(int32_t)((camera.y-track.origin_y)*8);
    int angle=(int)((camera_heading-PI/2)*512/TAU);REG32(ADDR_CAMERA_ANGLE_Y)=(angle&511)*4;
    REG32(ADDR_LIGHT_X)=-90;REG32(ADDR_LIGHT_Y)=-180;REG32(ADDR_LIGHT_Z)=-90;
    REG32(ADDR_USE_GOURAUD)=0xffffffffu;REG32(ADDR_USE_PHRASE)=0;
}
static void hud(unsigned joy){
    memset((void*)TXT_SCREEN,0,48*40);
    txt(0,0,"TRIGGER RALLY / ATARI JAGUAR");
    /* Visible completed-GPU-frame count, also used by the desktop regression.
     * Unlike emulator FPS/VBL, this advances only after an actual scene swap. */
    txt(0,34,"GPU");number(0,38,T->gpu_frames,6);
    if(state==MENU){
        txt(1,0,"TRACK:");txt(1,7,track.name);txt(2,0,"CAR:");txt(2,7,vehicle.cfg->name);
        txt(3,0,"L/R TRACK  U/D CAR  A RACE  1 REPLAY");txt(4,0,"NATIVE 3D / CODE ARTEMIS + 42BASTIAN");
    }else{
        txt(1,0,state==COUNTDOWN?"READY":state==PAUSED?"PAUSED":state==FINISHED?"FINISH":state==REPLAY?"REPLAY":"RACING");
        if(state==COUNTDOWN)number(1,8,(unsigned)maxf(1,countdown+1),1);
        txt(1,12,"CP");number(1,15,next_cp,2);txt(1,17,"/");number(1,18,track.cp_count,2);
        txt(1,23,"TIME");unsigned ms=(unsigned)(maxf(0,race_time)*100);number(1,28,ms/6000,2);txt(1,30,":");number(1,31,ms/100%60,2);txt(1,33,".");number(1,34,ms%100,2);
        txt(2,0,"KM/H");number(2,5,(unsigned)(length(vehicle.body.vel)*3.6f),3);txt(2,10,"GEAR");if(vehicle.gear<0)txt(2,15,"R");else number(2,15,vehicle.gear,1);
        txt(2,18,"RPM");number(2,22,(unsigned)(vehicle.engine_smoothed*60/TAU),4);txt(2,30,"GPU");number(2,34,T->gpu_frames,5);
        if(state==FINISHED){txt(3,0,"A RACE AGAIN  1 REPLAY  OPTION MENU");txt(4,0,"BEST");number(4,5,(unsigned)(best[track_id][car_id]*100),6);}
        else if(state==PAUSED){txt(3,0,"PAUSE TO RESUME / OPTION TO MENU");txt(4,0,"SIMULATION STOPPED; RENDERER RUNNING");}
        else{txt(3,0,"A GAS B BRAKE C HANDBRAKE  PAUSE");txt(4,0,"3 RESTART  0 RECOVER  2 CAMERA  OPTION MENU");}
    }
    T->input=joy;
}
static void telemetry(void){
    T->cpu_frames++;T->state=state;T->track=track_id;T->car=car_id;T->checkpoint=next_cp;T->time_ms=(unsigned)(maxf(0,race_time)*1000);
    T->speed_q16=(unsigned)(length(vehicle.body.vel)*65536);T->x_q16=(int32_t)(vehicle.body.pos.x*65536);T->y_q16=(int32_t)(vehicle.body.pos.y*65536);T->z_q16=(int32_t)(vehicle.body.pos.z*65536);T->recorded_frames=recorded;
    T->forward_x_q16=(int32_t)(vehicle.body.matrix[2]*65536);T->forward_y_q16=(int32_t)(vehicle.body.matrix[5]*65536);
}
static void progress(float dt){
    if(next_cp>=track.cp_count)return;const Checkpoint*cp=track.cp+next_cp;
    float dx=vehicle.body.pos.x-cp->pos.x,dy=vehicle.body.pos.y-cp->pos.y;float d=dx*dx+dy*dy;
    if(d<18*18){
        float time=race_time;if(last_cp_distance>=0){float a=sqrtf_local(last_cp_distance),b=sqrtf_local(d);if(a!=b)time-=dt*(a-18)/(a-b);}
        next_cp++;last_cp_distance=-1;sfx("checkpoint",70);
        if(next_cp==track.cp_count){race_time=maxf(0,time);state=FINISHED;float*besttime=&best[track_id][car_id];if(*besttime==0||race_time<*besttime)*besttime=race_time;sfx("kaching",60);}
    }else last_cp_distance=d;
}
static void update(unsigned joy,unsigned pressed,float dt){
    if(pressed&JOY_OPTION){state=MENU;load_track();return;}
    if(pressed&JOY_2)camera_mode^=1;
    if(state==MENU){
        unsigned oldtrack=track_id,oldcar=car_id;
        if(pressed&JOY_LEFT)track_id=(track_id+ASSETS->track_count-1)%ASSETS->track_count;
        if(pressed&JOY_RIGHT)track_id=(track_id+1)%ASSETS->track_count;
        if(pressed&(JOY_UP|JOY_DOWN))car_id^=1;
        if(oldtrack!=track_id||oldcar!=car_id){recorded=0;load_track();}
        if(pressed&JOY_A)restart();
    }else if(state==PAUSED){if(pressed&JOY_PAUSE)state=previous_state;}
    else if((pressed&JOY_PAUSE)&&(state==RACING||state==COUNTDOWN||state==REPLAY)){previous_state=state;state=PAUSED;}
    else if(pressed&JOY_3)restart();
    else if(state==FINISHED){if(pressed&JOY_A)restart();}
    if((pressed&JOY_1)&&recorded>1){state=REPLAY;replay_cursor=0;replay_accum=0;}
    if(state==REPLAY){
        replay_accum+=dt;
        while(replay_cursor+1<recorded&&replay_accum>=recording[replay_cursor].dt){replay_accum-=recording[replay_cursor].dt;replay_cursor++;}
        vehicle.body.pos=recording[replay_cursor].pos;vehicle.body.ori=recording[replay_cursor].ori;qmatrix(vehicle.body.ori,vehicle.body.matrix);
        if(replay_cursor+1>=recorded)state=FINISHED;
    }
    if(state!=COUNTDOWN&&state!=RACING)return;
    vehicle.input.throttle=(joy&(JOY_A|JOY_UP))?1:0;vehicle.input.brake=(joy&(JOY_B|JOY_DOWN))?1:0;vehicle.input.handbrake=(joy&JOY_C)?1:0;
    vehicle.input.turn=((joy&JOY_LEFT)?1:0)-((joy&JOY_RIGHT)?1:0);
    if(pressed&JOY_0){vehicle.recover_timer=vehicle.cfg->recover_trigger;}
    accumulator+=dt;
    while(accumulator>=1.f/SIM_HZ){
        accumulator-=1.f/SIM_HZ;
        vehicle.disabled=state==COUNTDOWN||vehicle.recovering;
        vehicle_step(&vehicle,1.f/SIM_HZ);
        if(state==COUNTDOWN){countdown-=1.f/SIM_HZ;if(countdown<=0){state=RACING;race_time=0;}}
        else if(state==RACING){race_time+=1.f/SIM_HZ;progress(1.f/SIM_HZ);}
    }
    if(state==RACING&&recorded<REPLAY_CAP){recording[recorded++]=(ReplayFrame){vehicle.body.pos,vehicle.body.ori,dt};}
    /* World boundary is a recoverable edge of the cropped native map. */
    if(vehicle.body.pos.x<track.origin_x+8||vehicle.body.pos.x>track.origin_x+1016||vehicle.body.pos.y<track.origin_y+8||vehicle.body.pos.y>track.origin_y+1016){load_track();state=COUNTDOWN;recorded=0;}
}
void game_main(void){
    typedef char car_abi_check[sizeof(CarConfig)==612?1:-1];
    typedef char track_abi_check[sizeof(Track)==108?1:-1];
    typedef char mesh_abi_check[sizeof(Mesh)==80?1:-1];
    typedef char object_abi_check[sizeof(GPUObject)==92?1:-1];
    typedef char scenery_cache_check[sizeof(CachedScene)==96?1:-1];
    memset((void*)0x400,0,0x1c00);memset((void*)0x110000,0,0x200000-0x110000);
    T->magic=0x54524a31;T->command=2;
    if(ASSETS->magic!=ASSET_MAGIC||ASSETS->version!=1){T->error=1;for(;;){REG16(0xf00058)=0xf0ff;}}
    copy_longs((void*)ADDR_texture,ASSETS->textures,ASSETS->texture_count*8192);
    copy_longs((void*)0x2000,gpu_blob,gpu_blob_end-gpu_blob);
#ifndef __JRISC__
    copy_longs((void*)0xf1b000,audio_blob,audio_blob_end-audio_blob);
#endif
    REG32(0xf005fc)=0x880a88ff;REG32(0xf00400)=0x880088ff;
    load_track();build_scene(.1f);hud(0);
    REG32(0xf02100)=0x7e00;REG32(0xf02110)=0x2000;REG32(0xf02114)=1;
#ifndef __JRISC__
    REG32(0xf1a100)=0x7e00;REG32(0xf1a110)=0xf1b100;REG32(0xf1a114)=1;
#endif
    engine_sound=sound("engine1");skid_sound=sound("scrape2");play(0,engine_sound,12,70,1);play(1,skid_sound,0,256,1);
    while(T->command!=0){TR_IDLE();}
    last_vbl=T->vbl;
    float scene_dt=1.f/60;unsigned scene_joy=0;
    for(;;){
        /* Tom renders the immutable submitted descriptors while Jerry computes
           the NEXT physical pose. Terrain-changing menu actions wait first. */
        build_scene(scene_dt);hud(scene_joy);audio_update();telemetry();
        TR_FENCE();T->command=1;
        unsigned vbl=T->vbl,dv=vbl-last_vbl;last_vbl=vbl;
        float dt=clampf(dv/((REG16(0xf14002)&0x10)?60.f:50.f),1.f/60,.1f);
        unsigned joy=joy_read(),pressed=joy&~last_joy;last_joy=joy;
        if(state==MENU&&(pressed&(JOY_LEFT|JOY_RIGHT|JOY_UP|JOY_DOWN)))while(T->command){TR_IDLE();}
        update(joy,pressed,dt);
        while(T->command){TR_IDLE();}
        scene_dt=dt;scene_joy=joy;
    }
}
