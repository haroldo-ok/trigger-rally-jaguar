#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Convert the actual Trigger Rally offline data, not replacement demo assets.

Three.js JSON v3 bit-field faces, scene transforms, UVs/materials, all vehicle
configs, all three shipped courses, terrain deformation, textures and all Ogg
samples are decoded here. Full topology and a geometry-derived Jaguar LOD are
both retained. Generated manifest records every input, transformation and use.
The source game's content license is NOT GPL; see licenses/TriggerRally-terms.md.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parents[1]
BASE=0x840000
N=128; STEP=8.; SCALE=8.

class Pack:
    def __init__(self): self.data=bytearray(4096)
    def add(self,b,alignment=8):
        self.data.extend(b'\0'*((-len(self.data))%alignment)); p=BASE+len(self.data)
        self.data.extend(b); return p
    def record(self,fmt,*args): return self.add(struct.pack('>'+fmt,*args))

def text(s,n): return s.encode('ascii','replace')[:n-1].ljust(n,b'\0')
def be(a,kind='i2'): return np.asarray(a).astype('>'+kind).tobytes()
def cat(a,b,c,d,t): return b+.5*t*(c-a+t*(2*a-5*b+4*c-d+t*(3*(b-c)+d-a)))
def unit(v): return v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-12)

class Converter:
    def __init__(self,public,out):
        self.pub=public; self.out=out; self.pack=Pack(); self.inputs={}; self.meshes=[];self.textures=[]; self.mesh_ids={};self.tex_ids={};self.missing=[]
        pal=np.array(json.loads((ROOT/'tools/cry_palette.json').read_text()),dtype=float).T
        y=np.arange(256,dtype=float)[None,:,None]/256
        rgb=(pal[:,None,:]*y).astype(np.uint8).reshape(-1,3)
        self.color_tree=cKDTree(rgb); self.colors=rgb
    def load(self,rel):
        p=self.pub/rel
        b=p.read_bytes();self.inputs[rel]={'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
        return b
    def js(self,rel): return json.loads(self.load(rel))
    def cry(self,rgb):
        a=np.asarray(rgb);return self.color_tree.query(a.reshape(-1,3))[1].astype(np.uint16).reshape(a.shape[:-1])
    def texture(self,rel):
        if rel in self.tex_ids:return self.tex_ids[rel]
        b=self.load(rel); im=Image.open(self.pub/rel).convert('RGBA').resize((64,64),Image.Resampling.LANCZOS)
        a=np.array(im);rgb=a[:,:,:3].copy();pixels=self.cry(rgb)
        # Jaguar source-data comparator makes CRY zero transparent. Do not
        # invent an opaque backdrop for the original alpha-tested vegetation.
        pixels[pixels==0]=0x8801;pixels[a[:,:,3]<80]=0
        idx=len(self.textures);self.tex_ids[rel]=idx;self.textures.append(be(pixels,'u2'));return idx
    def geometry(self,g,mat_default,scene_materials=None):
        v=np.array(g['vertices'],dtype=float).reshape(-1,3)/float(g.get('scale',1))
        uv=[np.array(u,dtype=float).reshape(-1,2) for u in g.get('uvs',[]) if u]
        f=g['faces'];i=0;result=[]
        while i<len(f):
            flags=f[i];i+=1; count=4 if flags&1 else 3
            ids=f[i:i+count];i+=count
            mat=f[i] if flags&2 else 0;i+=bool(flags&2)
            faceuv=[];vertexuv=[]
            if flags&4:
                for layer in uv:faceuv.append(f[i]);i+=1
            if flags&8:
                for layer in uv:vertexuv.append(f[i:i+count]);i+=count
            if flags&16:i+=1
            if flags&32:i+=count
            if flags&64:i+=1
            if flags&128:i+=count
            m=g.get('materials',[])
            material=m[mat] if m and mat<len(m) and isinstance(m[mat],dict) else mat_default
            texture=material.get('_tex',-1)
            diffuse=material.get('colorDiffuse',material.get('color',[.7,.7,.7]))
            if isinstance(diffuse,int):diffuse=[(diffuse>>16&255)/255,(diffuse>>8&255)/255,(diffuse&255)/255]
            rgb=np.array(diffuse[:3])*255
            col=int(self.cry(rgb[None,:])[0]);col=(col&0xff00)|0x40
            for tri in ((0,1,3),(1,2,3)) if count==4 else ((0,1,2),):
                uvs=[uv[0][vertexuv[0][t]] for t in tri] if vertexuv and uv else [[0,0]]*3
                result.append((tuple(ids[t] for t in tri),texture,uvs,col))
        assert i==len(f)
        return v,result
    def material(self,m,base):
        m=dict(m); tex=m.get('mapDiffuse',m.get('map'))
        if tex:
            p=(base/tex).resolve()
            if p.exists() and p.is_relative_to(self.pub.resolve()):m['_tex']=self.texture(str(p.relative_to(self.pub.resolve())))
        return m
    def mesh(self,name,rel,kind='scene'):
        d=self.js(rel); parts=[];texmap={};md={}
        if 'objects' in d:
            for k,t in d.get('textures',{}).items():
                p=self.pub/t['url'].lstrip('/') if t['url'].startswith('/') else (self.pub/rel).parent/t['url']
                if p.exists():texmap[k]=self.texture(str(p.resolve().relative_to(self.pub.resolve())))
                else:
                    found=list(self.pub.rglob(Path(t['url']).name))
                    if not found:
                        self.missing.append({'reference':t['url'],'referenced_by':rel,'handling':'original material diffuse color; no substitute texture invented'})
                        texmap[k]=-1
                    else:texmap[k]=self.texture(str(found[0].relative_to(self.pub)))
            for k,m in d.get('materials',{}).items():
                p=m.get('parameters',{});md[k]={'color':p.get('color',0xc0c0c0),'_tex':texmap.get(p.get('map'),-1)}
            for objname,o in d['objects'].items():
                if 'geometry' not in o:continue
                geom=d['embeds'][d['geometries'][o['geometry']]['id']]
                v,f=self.geometry(geom,md.get(o.get('material'),{}))
                scale=np.array(o.get('scale',[1,1,1]));v*=scale
                q=o.get('quaternion',[0,0,0,1]);x,y,z,w=q
                rot=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)], [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)], [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
                v=v@rot.T+np.array(o.get('position',[0,0,0]))
                # Icarus source scene is Z up; RenderCar rotates the scene -90° about X.
                if name=='icarus': v=v[:,[0,2,1]]*np.array([1,1,-1])
                parts.append((objname,v,f))
        else:
            for m in d.get('materials',[]):m.update(self.material(m,(self.pub/rel).parent))
            v,f=self.geometry(d,{'colorDiffuse':[.7,.7,.7]});parts=[(name,v,f)]
        # A complete combined mesh keeps EVERY scene child; also retain articulated
        # Icarus children independently for the native wing-fold implementation.
        verts=[];faces=[];part_ranges=[];offset=0
        for pn,v,f in parts:
            verts.extend(v);faces.extend([(tuple(j+offset for j in ids),t,u,c) for ids,t,u,c in f]);part_ranges.append((pn,len(v),len(f)));offset+=len(v)
        vertices=np.array(verts);full=self.encode_mesh(vertices,faces)
        lodv,lodf=self.lod(vertices,faces,450 if name in ('arbusu','icarus') else 130)
        low=self.encode_mesh(lodv,lodf)
        idx=len(self.meshes);self.mesh_ids[name]=idx
        self.meshes.append({'name':name,'record':text(name,32)+struct.pack('>12I',len(lodv),len(lodf),*low,*full,len(vertices),len(faces)), 'source':rel,'parts':part_ranges,'full_vertices':len(vertices),'full_triangles':len(faces),'lod_vertices':len(lodv),'lod_triangles':len(lodf)})
        return idx
    def checkpoint_mesh(self):
        # Exact authored geometry from client/misc.js, not a replacement arch:
        # three 32-segment radius-16 open cylinders, X=1.1, Z=0/120/240 deg.
        self.load('scripts/client/misc.js')
        vertices=[];faces=[];col=(int(self.cry(np.array([[16,48,16]]))[0])&0xff00)|0x70
        for ring in range(3):
            az=ring*2*math.pi/3;cx,sx=math.cos(1.1),math.sin(1.1);cz,sz=math.cos(az),math.sin(az)
            rot=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])@np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
            raw=np.array([[16*math.sin(i*2*math.pi/32),y,16*math.cos(i*2*math.pi/32)] for y in (-.5,.5) for i in range(32)])@rot.T
            for side in (0,1):
                offset=len(vertices);vertices.extend(raw)
                for i in range(32):
                    j=(i+1)%32
                    for ids in ((i,j,i+32),(j,j+32,i+32)):
                        if side:ids=tuple(reversed(ids))
                        faces.append((tuple(offset+k for k in ids),-1,[[0,0]]*3,col))
        full=self.encode_mesh(np.array(vertices),faces);idx=len(self.meshes);self.mesh_ids['checkpoint']=idx
        self.meshes.append({'name':'checkpoint','record':text('checkpoint',32)+struct.pack('>12I',len(vertices),len(faces),*full,*full,len(vertices),len(faces)), 'source':'scripts/client/misc.js','parts':[('three double-sided rings',len(vertices),len(faces))], 'full_vertices':len(vertices),'full_triangles':len(faces),'lod_vertices':len(vertices),'lod_triangles':len(faces)})
    def vegetation_material(self):
        # The original has no grass photograph: it uses this two-colour shader.
        # Bake its vegetation colours/detail normal illumination for Jaguar CRY.
        self.load('scripts/client/terrain.js');rel='a/textures/heightdetail1.jpg';self.load(rel)
        detail=np.asarray(Image.open(self.pub/rel).convert('L').resize((64,64)),dtype=float)/255
        gy,gx=np.gradient(detail);normal=unit(np.stack([-gx*12,-gy*12,np.ones_like(gx)],axis=-1))
        a=np.clip(normal[:,:,2]*.7+.3,.01,1);mix=.7/((1/a-2)*.3+1)
        rgb=(np.array([.43,.45,.25])[None,None,:]*(1-mix[:,:,None])+np.array([.14,.18,.05])[None,None,:]*mix[:,:,None])*255
        idx=len(self.textures);self.tex_ids['shader/terrain-vegetation']=idx;self.textures.append(be(self.cry(rgb),'u2'))
    def lod(self,v,f,target):
        if len(f)<=target:return v,f
        bounds=np.ptp(v,axis=0); resolution=40
        best=(v,f)
        while resolution>=3:
            step=max(bounds)/resolution
            cells=np.floor((v-v.min(axis=0))/max(step,1e-5)).astype(int)
            _,mapping=np.unique(cells,axis=0,return_inverse=True)
            sums=np.zeros((mapping.max()+1,3));np.add.at(sums,mapping,v)
            out=sums/np.bincount(mapping)[:,None];fs=[];seen=set()
            for ids,t,u,c in f:
                ids2=tuple(int(mapping[j]) for j in ids)
                if len(set(ids2))!=3 or ids2 in seen:continue
                seen.add(ids2);fs.append((ids2,t,u,c))
            best=(out,fs)
            if len(fs)<=target:break
            resolution-=1
        return best
    def encode_mesh(self,v,faces):
        points=np.column_stack([np.rint(v*SCALE).astype(int),np.zeros(len(v),int)])
        pp=self.pack.add(struct.pack('>I',len(v))+be(points))
        ns=[];vn=np.zeros_like(v);bf=bytearray(struct.pack('>I',len(faces)));uvdata=[]
        # Engine normals point INTO the solid (positive dot with point-camera).
        for ids,t,u,c in faces:
            a,b,d=v[list(ids)];normal=-unit(np.cross(b-a,d-a));ns.append(normal)
            for j in ids:vn[j]+=normal
            if t>=0:
                uv=np.clip(np.array(u)*63*256,0,63*256).astype(int)
                uvptr=self.pack.add(struct.pack('>HH6H',t,0,*uv.reshape(-1)))
            else:uvptr=0
            bf.extend(struct.pack('>4HI',*ids,c,uvptr))
        fp=self.pack.add(bf)
        nptr=self.pack.add(struct.pack('>I',len(faces))+be(np.column_stack([np.rint(np.array(ns)*256),np.zeros(len(ns))])))
        vp=self.pack.add(struct.pack('>I',len(v))+be(np.column_stack([np.rint(unit(vn)*256),np.zeros(len(v))])))
        return pp,fp,nptr,vp
    def terrain(self,d):
        img=np.array(Image.open(self.pub/'a/tracks/nice.png').convert('RGB'))[::-1].astype(float)
        height=(img[:,:,0]+img[:,:,1]*256)*.25; surface=np.full(height.shape,25.,dtype=float)
        cps=d['config']['course']['checkpoints'];pos=np.array([p['pos'] for p in cps]);pts=np.vstack([2*pos[0]-pos[1],pos,2*pos[-1]-pos[-2]])
        def circle(arr,x,y,value,r,hard,alpha):
            xx=np.arange(math.ceil((x-r)/7.5),math.floor((x+r)/7.5)+1)
            yy=np.arange(math.ceil((y-r)/10.8),math.floor((y+r)/10.8)+1)
            xxg,yyg=np.meshgrid(xx*7.5-x,yy*10.8-y)
            radius=np.sqrt(xxg*xxg+yyg*yyg)/r
            weight=np.clip((1-radius)/max(1-hard,1e-9),0,1);weight=weight*weight*(3-2*weight)
            ix=np.ix_(yy%1024,xx%1024);arr[ix]+=(value-arr[ix])*weight*alpha
        for attr,arr in [('surf',surface),('disp',height)]:
            rem=0.
            for i in range(len(pos)-1):
                length=np.linalg.norm(pos[i+1,:2]-pos[i,:2]);t=rem
                while t<length:
                    u=t/length;p=cat(*pts[i:i+4],u);cfg={k:(1-u)*cps[i][attr][k]+u*cps[i+1][attr][k] for k in ('radius','hardness','strength')}
                    if cfg['radius']>0 and cfg['strength']>0:circle(arr,p[0]-(3.75 if attr=='surf' else 0),p[1]-(5.4 if attr=='surf' else 0),0 if attr=='surf' else p[2],cfg['radius'],cfg['hardness'],cfg['strength'])
                    t+=max(0,cfg['radius'])/3+3
                rem=t-length
        start=d['config']['course']['startposition']['pos'];middle=(pos[:,:2].min(0)+pos[:,:2].max(0))/2
        origin=np.floor((middle-STEP*N/2)/STEP)*STEP
        xs=(origin[0]+np.arange(N)*STEP)/7.5;ys=(origin[1]+np.arange(N)*STEP)/10.8
        def sample(a):
            x,y=np.meshgrid(xs,ys);fx=np.floor(x).astype(int);fy=np.floor(y).astype(int);u=x-fx;v=y-fy
            return (a[fy%1024,fx%1024]*(1-u)*(1-v)+a[fy%1024,(fx+1)%1024]*u*(1-v)+a[(fy+1)%1024,fx%1024]*(1-u)*v+a[(fy+1)%1024,(fx+1)%1024]*u*v)
        heights=sample(height);surf=sample(surface)
        # Palette entries select dirt vs grass textures in createplane.inc.
        color=np.where(surf<9,0x8040,0x7f40).astype(np.uint16)
        gy,gx=np.gradient(heights,STEP,STEP)
        vertex=unit(np.stack([gx,-np.ones_like(gx),gy],axis=-1))
        # Exactly the two triangle planes used by the renderer at each grid cell.
        h=heights*SCALE;right=np.roll(h,-1,1);down=np.roll(h,-1,0);diag=np.roll(down,-1,1)
        n0=unit(np.stack([diag-down,-np.full_like(h,STEP*SCALE),diag-right],axis=-1))
        n1=unit(np.stack([right-h,-np.full_like(h,STEP*SCALE),down-h],axis=-1))
        normals=np.stack([n0,n1],axis=2)
        def packednorm(a): return be(np.concatenate([np.zeros((*a.shape[:-1],1)),np.rint(a*256)],axis=-1))
        hp=self.pack.add(be(np.rint(heights*SCALE)))
        cp=self.pack.add(be(color,'u2'));np_=self.pack.add(packednorm(normals));vp=self.pack.add(packednorm(vertex));sp=self.pack.add(be(np.rint(surf),'u1'))
        self.out.mkdir(parents=True,exist_ok=True)
        rgb=self.colors[color].astype(np.uint8);Image.fromarray(rgb).save(self.out/(d['id']+'-terrain.png'))
        return origin,(hp,cp,np_,vp,sp)
    def track(self,rel):
        d=self.js(rel);origin,maps=self.terrain(d);c=d['config']['course'];cps=c['checkpoints']
        cb=b''.join(struct.pack('>9f',*p['pos'],p['surf']['radius'],p['surf']['hardness'],p['surf']['strength'],p['disp']['radius'],p['disp']['hardness'],p['disp']['strength']) for p in cps)
        cpp=self.pack.add(cb);sc=[]
        mapping={'arches':'arch','chevrons':'chevron','woodenfence':'fence','conifer-1':'tree','conifer-2':'tree'}
        for layer,settings in d['config'].get('scenery',{}).items():
            for o in settings.get('add',[]):sc.append((o['pos'],o.get('rot',[0,0,0]),o.get('scale',1),mapping[layer],1 if layer=='arches' else 2 if layer.startswith('conifer') else 3 if layer=='woodenfence' else 4))
        # Bake deterministic environment-density trees, with a fixed LFIB-derived
        # offline seed; placements are adapted, not identical to browser tiling.
        rng=np.random.default_rng(0x5452+sum(map(ord,d['id'])))
        for _ in range(120):
            x,y=origin+rng.uniform(170,850,size=2);u=(x-origin[0])/STEP;v=(y-origin[1])/STEP
            h=np.frombuffer(self.pack.data[maps[0]-BASE:maps[0]-BASE+32768],dtype='>i2').reshape(N,N)
            ix=int(u)%N;iy=int(v)%N
            # Keep the course clear; explicit hand-placed trees are untouched.
            if min(np.linalg.norm(np.array(p['pos'][:2])-[x,y]) for p in cps)<30:continue
            sc.append(([float(x),float(y),float(h[iy,ix])/SCALE],[0,0,float(rng.uniform(0,2*math.pi))],float(rng.uniform(.8,1.8)),'tree',2))
        sb=b''.join(struct.pack('>7f2I',*p,*r,s,self.mesh_ids[m],l) for p,r,s,m,l in sc)
        scp=self.pack.add(sb)
        record=text(d['id'],16)+text(d.get('name',d['id']),32)+struct.pack('>6f9I',*origin,*c['startposition']['pos'],c['startposition']['rot'][2],len(cps),len(sc),*maps,cpp,scp)
        return record,{'id':d['id'],'name':d.get('name'),'checkpoints':len(cps),'explicit_scenery':sum(len(s.get('add',[])) for s in d['config'].get('scenery',{}).values()),'scenery':len(sc),'origin':origin.tolist(),'map_step_m':STEP,'map_coverage_m':N*STEP}
    def car(self,rel):
        d=self.js(rel);c=d['config'];e=c['engine'];t=c['transmission'];b=bytearray(text(d['name'],32));b+=struct.pack('>9f6I',c['mass'],*c['dimensions'],*c['center'],c['recover']['triggerTime'],c['recover']['releaseTime'],int(c.get('wings',False)),len(c['wheels']),len(c['clips']),len(e['powerband']),len(t['forward']),0)[:-4]
        for i in range(4):
            w=c['wheels'][i] if i<len(c['wheels']) else {}
            b+=struct.pack('>8fI',*w.get('pos',[0,0,0]),*[w.get(k,0) for k in ('radius','drive','turn','brake','handbrake')],w.get('flip',0))
        for i in range(16):
            clip=c['clips'][i] if i<len(c['clips']) else {};b+=struct.pack('>4f',*clip.get('pos',[0,0,0]),clip.get('radius',0))
        for i in range(8):
            p=e['powerband'][i] if i<len(e['powerband']) else {};b+=struct.pack('>2f',p.get('rpm',0),p.get('power',0))
        b+=struct.pack('>5f',e['powerscale'],e['redline'],e['flywheel'],t['reverse'],t['final'])
        b+=struct.pack('>8f',*(t['forward']+[0]*8)[:8]);b+=struct.pack('>2I',self.mesh_ids['icarus' if c.get('wings') else 'arbusu'],self.mesh_ids['wheel'])
        assert len(b)==612,len(b)
        return b
    def run(self):
        self.load('a/tracks/nice.png');self.js('v1/envs/alp')
        for name,rel in [('arbusu','a/meshes/car1-body.json'),('wheel','a/meshes/car1-wheel.json'),('icarus','a/meshes/icarus-body.json'),('arch','a/meshes/arch.r54.js'),('chevron','a/meshes/chevron.r54.js'),('tree','a/scenery/tree36/tree36.js'),('fence','a/scenery/wood_el1/wood_el1.js')]:self.mesh(name,rel)
        # Include every texture, not just those referenced by meshes.
        for p in sorted((self.pub/'a').rglob('*')):
            if p.suffix.lower() in ('.jpg','.png') and 'tracks' not in p.parts:self.texture(str(p.relative_to(self.pub)))
        self.checkpoint_mesh();self.vegetation_material()
        meshp=self.pack.add(b''.join(m['record'] for m in self.meshes))
        texturesp=self.pack.add(b''.join(self.textures))
        trackrecords=[];tracks=[]
        for name in ('uUJTPz6M','RF87t6b6','v3base2'):
            r,m=self.track('v1/tracks/'+name);trackrecords.append(r);tracks.append(m)
        trackp=self.pack.add(b''.join(trackrecords))
        carp=self.pack.add(b''.join(self.car('v1/cars/'+name) for name in ('ArbusuG','Icarus')))
        samples=[];samples_manifest=[]
        for f in sorted((self.pub/'a/sounds').glob('*.ogg')):
            rel=str(f.relative_to(self.pub));self.load(rel)
            pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(f),'-f','s16be','-ac','1','-ar','8000','-'])
            p=self.pack.add(pcm);samples.append(text(f.stem,32)+struct.pack('>3I',p,len(pcm)//2,8000));samples_manifest.append({'name':f.stem,'samples':len(pcm)//2,'rate':8000})
        sp=self.pack.add(b''.join(samples))
        header=struct.pack('>13I',0x54524a31,1,3,2,len(self.meshes),len(self.textures),len(samples),len(self.pack.data),trackp,carp,meshp,texturesp,sp)
        self.pack.data[:len(header)]=header
        (self.out/'assets.bin').write_bytes(self.pack.data)
        defines={f'MESH_{k.upper()}':v for k,v in self.mesh_ids.items()}
        stems=[re.sub('[^A-Z0-9]','_',Path(k).stem.upper()) for k in self.tex_ids]
        for (k,v),stem in zip(self.tex_ids.items(),stems):
            name=stem if stems.count(stem)==1 else re.sub('[^A-Z0-9]','_',k.upper())
            defines['TEX_'+name]=v
        (self.out/'asset_ids.h').write_text('/* Generated from the real upstream assets. */\n'+'\n'.join(f'#define {k} {v}' for k,v in defines.items())+'\n')
        (self.out/'asset_ids.inc').write_text('; Generated asset IDs for the actual converted data.\n'+'\n'.join(f'{k} equ {v}' for k,v in defines.items())+'\n')
        manifest={'format':1,'source_commit':'079ac53216b74598b652ce3bf11478beb5c6832b','content_license':'restricted; licenses/TriggerRally-terms.md','assets_bytes':len(self.pack.data),'tracks':tracks,'meshes':[{k:v for k,v in m.items() if k!='record'} for m in self.meshes],'textures':self.tex_ids,'samples':samples_manifest,'inputs':self.inputs,'missing_upstream_assets':self.missing,'adaptations':['64x64 CRY textures, no per-pixel normal mapping','8000 Hz mono PCM audio','128x128 local terrain windows at 8 metre spacing; bilinear collision sampling','Full mesh topology retained, runtime vertex-clustered LOD','Environment-density tree placements are deterministic adaptations, not identical to the browser LFIB tiler']}
        (self.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(f'Converted {len(self.inputs)} inputs, {len(self.meshes)} meshes, {len(self.textures)} textures, {len(samples)} sounds, 3 tracks, 2 vehicles: {len(self.pack.data):,} bytes')

def main():
    p=argparse.ArgumentParser();p.add_argument('--public',type=Path,default=ROOT.parent/'upstream/TriggerRally/server/public');p.add_argument('--out',type=Path,default=ROOT/'assets');a=p.parse_args();Converter(a.public.resolve(),a.out.resolve()).run()
if __name__=='__main__':main()
