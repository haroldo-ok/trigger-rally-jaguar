/* SPDX-License-Identifier: GPL-3.0-or-later
 * Big-endian cartridge asset ABI. tools/convert_assets.py writes these records.
 * All coordinates in this ABI are Trigger Rally's metres, Z up.
 */
#ifndef TR_DATA_H
#define TR_DATA_H
#include <stdint.h>
#define ASSET_BASE 0x840000u
#define ASSET_MAGIC 0x54524a31u
#define MAP_N 128
#define MAP_STEP 8
#define WORLD_SCALE 8
#define MAX_CP 64
#define MAX_SCENERY 512
#define MAX_MESH 32
#define MAX_TEXTURE 32
#define MAX_SAMPLES 16
#define MAX_SCENE_OBJECTS 32

typedef struct { float x,y,z; } V3;
typedef struct { float x,y,z,w; } Q4;
typedef struct { V3 pos; float radius,hardness,strength,disp_radius,disp_hardness,disp_strength; } Checkpoint;
typedef struct { V3 pos,rot; float scale; uint32_t mesh,layer; } Scenery;
typedef struct {
    char id[16],name[32];
    float origin_x,origin_y;
    V3 start; float heading;
    uint32_t cp_count,scenery_count;
    const int16_t *height;
    const uint16_t *color;
    const int16_t *normals,*vnormals;
    const uint8_t *surface;
    const Checkpoint *cp;
    const Scenery *scenery;
} Track;
typedef struct {
    char name[32];
    uint32_t vertices,triangles;
    const void *points,*faces,*normals,*vnormals;
    const void *full_points,*full_faces,*full_normals,*full_vnormals;
    uint32_t full_vertices,full_triangles;
} Mesh;
typedef struct { char name[32]; const int16_t *pcm; uint32_t length,rate; } Sample;
typedef struct { V3 pos; float radius,drive,turn,brake,handbrake; uint32_t flip; } WheelConfig;
typedef struct { V3 pos; float radius; } Clip;
typedef struct { float rpm,power; } PowerPoint;
typedef struct {
    char name[32];
    float mass; V3 dimensions,center;
    float recover_trigger,recover_release;
    uint32_t wings,wheel_count,clip_count,power_count,gear_count;
    WheelConfig wheels[4]; Clip clips[16]; PowerPoint power[8];
    float powerscale,redline,flywheel,reverse,final,gears[8];
    uint32_t body_mesh,wheel_mesh;
} CarConfig;
typedef struct {
    uint32_t magic,version,track_count,car_count,mesh_count,texture_count,sample_count,size;
    const Track *tracks; const CarConfig *cars; const Mesh *meshes;
    const uint16_t *textures; const Sample *samples;
} AssetHeader;
#define ASSETS ((const AssetHeader *)ASSET_BASE)
#endif
