;-*-asm-*-

****************
* compute rotation matrix
* a=cos(gamma) b=sin(gamma)
* c=cos(beta)  d=sin(beta)
* e=cos(alpha) f=sin(alpha)

rotated		reg 14

a		reg 99
b		reg 99
c		reg 99
d		reg 99
e		reg 99
f		reg 99
ac		reg 99
bc		reg 99

m1		reg 99	;
m2		reg 99	;
m3		reg c!	;          / df      -de       c  \
m4		reg 99	;          |                      |
m5		reg 99	; D(x,y,z)=| ac*f+be -ace+bf  -ad  |
m6		reg 99	;          |                      |
m7		reg 99	;          \ -bcf+ae bce+af   bd /
m8		reg 99	;
m9		reg 99	;

rotate_object::
; Native 68000 physics supplies the complete quaternion-derived 3x3 matrix.
; This removes Euler singularities and supports suspension roll/pitch and flight.
	move	curr_object,r14
	addq	#32,r14
	addq	#20,r14
	load	(r14),m1
	load	(r14+4),m2
	load	(r14+8),m3
	load	(r14+12),m4
	load	(r14+16),m5
	load	(r14+20),m6
	load	(r14+24),m7
	load	(r14+28),m8
	addq	#32,r14
	load	(r14),m9
object_scale.a reg 99
	load	(r14+4),tmp0
	moveta	tmp0,object_scale.a

	UNREG a,b,c,d,e,f,ac,bc

;---------------

counter		REG 99
LOOP		REG 99
x_pos		reg 99
y_pos		reg 99
z_pos		reg 99

x1		reg 99
y1		reg 99
z1		reg 99
xyz_ptr		reg 99
LR2		reg 99
mask		reg 99


	load	(curr_object),x_pos
	movefa	cam_x.a,tmp0
	load	(curr_object+obj_y),y_pos

	movei	#$ffff,mask
	move	mask,tmp3
	shrq	#2,tmp3		; $3fff

	shlq	#16,x_pos
	move	y_pos,z_pos
	sharq	#16,x_pos
	shlq	#16,z_pos
	sharq	#16,y_pos
	sharq	#16,z_pos
	movefa	cam_y.a,tmp1
	movefa	cam_z.a,tmp2
	sub	tmp0,x_pos
	sub	tmp1,y_pos
	load	(curr_object+obj_points),xyz_ptr
	sub	tmp2,z_pos
	load	(curr_object+obj_rotated),rotated
	movei	#._ret1,LR2
	movei	#rotate_points,tmp0
	jump	(tmp0)
	nop

._ret1:
	movei	#256,tmp0
	moveta	tmp0,object_scale.a ; normals are rotated, never scaled
	moveq	#0,x_pos	; normals are not moved
	moveq	#0,y_pos
	moveq	#0,z_pos

	load	(curr_object+obj_normals),xyz_ptr
	load	(curr_object+obj_normals_rotated),rotated
 IF GOURAUD = 1
	jr	rotate_points
	addq	#._ret2-._ret1,LR2

._ret2:
	load	(curr_object+obj_vnormals),xyz_ptr
	cmpq	#0,xyz_ptr
	movei	#rotate_camera1,LR2
	jump	eq,(LR2)
	load	(curr_object+obj_vnormals_rotated),rotated
 ELSE
	movei	#rotate_camera1,LR2
 ENDIF
***************
rotate_points:
	load	(xyz_ptr),counter
	addq	#4,xyz_ptr
	store	counter,(rotated)
	addq	#4,rotated

	load	(xyz_ptr),x1
	addqt	#4,xyz_ptr
	load	(xyz_ptr),z1
	addqt	#4,xyz_ptr

	move	pc,LOOP
	addq	#4,LOOP
.loop_xyz
	move	x1,y1
	sharq	#16,x1
	shlq	#16,y1
	sharq	#16,z1
	sharq	#16,y1

	movefa	object_scale.a,tmp0
	imult	tmp0,x1
	imult	tmp0,y1
	imult	tmp0,z1
	sharq	#8,x1
	sharq	#8,y1
	sharq	#8,z1

	imultn	m1,x1
	imacn	m2,y1
	imacn	m3,z1
	resmac	tmp0

	imultn	m4,x1
	imacn	m5,y1
	imacn	m6,z1
	resmac	tmp1

	imultn	m7,x1
	imacn	m8,y1
	imacn	m9,z1
	resmac	tmp2

	add	tmp3,tmp0
	add	tmp3,tmp1
	add	tmp3,tmp2

	sharq	#15,tmp0
	sharq	#15,tmp1
	sharq	#15,tmp2

	load	(xyz_ptr),x1
	addqt	#4,xyz_ptr
	add	x_pos,tmp0
	load	(xyz_ptr),z1
	shlq	#16,tmp0
	add	y_pos,tmp1
	addqt	#4,xyz_ptr
	and	mask,tmp1
	add	z_pos,tmp2
	or	tmp1,tmp0
	store	tmp0,(rotated)
	addq	#4,rotated
	shlq	#16,tmp2
	subq	#1,counter
	store	tmp2,(rotated)
	jump	ne,(LOOP)
	addqt	#4,rotated

	jump	(LR2)
	nop

	UNREG m1,m2,m3,m4,m5,m6,m7,m8,m9
	unreg object_scale.a

cam_sin		reg 99
neg_cam_sin	reg 99
cam_cos		reg 99
vertex_source	reg 99
normals_source	reg 99
vnormals_source	reg 99

rotate_camera::
	load	(curr_object),x_pos
	movefa	cam_x.a,tmp0
	movefa	cam_y.a,tmp1
	load	(curr_object+obj_y),y_pos
	movefa	cam_z.a,tmp2

	shlq	#16,x_pos
	move	y_pos,z_pos
	sharq	#16,x_pos
	shlq	#16,z_pos
	sharq	#16,y_pos
	sharq	#16,z_pos

	sub	tmp0,x_pos
	sub	tmp1,y_pos
	sub	tmp2,z_pos

	load	(curr_object+obj_points),vertex_source
	load	(curr_object+obj_normals),normals_source
	jr	rotate_cont
	load	(curr_object+obj_vnormals),vnormals_source

rotate_camera1::
	load	(curr_object+obj_rotated),vertex_source
	load	(curr_object+obj_normals_rotated),normals_source
	load	(curr_object+obj_vnormals_rotated),vnormals_source
rotate_cont
	movefa	cam_cos.a,cam_cos
	movefa	cam_sin.a,cam_sin
	movefa	neg_cam_sin.a,neg_cam_sin

	move	vertex_source,xyz_ptr
	load	(curr_object+obj_rotated),rotated
	move	pc,LR2
	jr	rc_points
	addq	#6,LR2

._ret1:
	moveq	#0,x_pos	; normals are not moved
	moveq	#0,y_pos
	moveq	#0,z_pos

	move	normals_source,xyz_ptr
	load	(curr_object+obj_normals_rotated),rotated
	move	LR,LR2

rc_points:
	load	(xyz_ptr),counter
	addq	#4,xyz_ptr
	store	counter,(rotated)
	addq	#4,rotated


	load	(xyz_ptr),x1
	addq	#4,xyz_ptr
	load	(xyz_ptr),z1
	addq	#4,xyz_ptr

	move	pc,LOOP
	addq	#4,LOOP
.loop_xyz
	move	x1,y1
	sharq	#16,x1
	shlq	#16,y1
	sharq	#16,z1
	sharq	#16,y1

	add	x_pos,x1
	add	y_pos,y1
	add	z_pos,z1

	imultn	cam_cos,x1
	imacn	cam_sin,z1
	resmac	tmp0

	imultn	neg_cam_sin,x1
	imacn	cam_cos,z1
	resmac	tmp1

	add	tmp3,tmp0	; x
	add	tmp3,tmp1	; z
	sharq	#15,tmp0
	sharq	#15,tmp1
	shlq	#16,tmp0
	shlq	#16,tmp1

	load	(xyz_ptr),x1
	addqt	#4,xyz_ptr
	and	mask,y1
	load	(xyz_ptr),z1
	or	y1,tmp0
	addq	#4,xyz_ptr
	store	tmp0,(rotated)
	addq	#4,rotated
	subq	#1,counter
	store	tmp1,(rotated)
	jump	ne,(LOOP)
	addqt	#4,rotated

	jump	(LR2)
	nop

	UNREG rotated
	unreg xyz_ptr,x1,y1,z1,counter
	unreg LOOP,LR2
	unreg x_pos,y_pos,z_pos
	unreg cam_sin, neg_cam_sin, cam_cos
	unreg vertex_source, normals_source, vnormals_source
	unreg mask
