"""Cycles studio renders of the Hybrid Matrix GLB exported from the three.js viewer.

usage: python3 hm_render.py -- <variant> <glb> <outdir> <shots,comma> [scale] [samples]
variant: steel | leather | amphead
"""
import bpy, sys, math, os
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
VARIANT, GLB, OUT, SHOTS = argv[0], argv[1], argv[2], argv[3].split(',')
SCALE = float(argv[4]) if len(argv) > 4 else 1.0
SAMPLES = int(argv[5]) if len(argv) > 5 else 160
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# lineup: VARIANT='lineup', GLB='amphead.glb,leather.glb,steel.glb' placed side by side
PARTS = []  # (variant, [objects])
glbs = GLB.split(',')
names = {'poliigon': 'steel'}
for i, g in enumerate(glbs):
    before = set(sc.objects)
    bpy.ops.import_scene.gltf(filepath=g)
    new = [o for o in sc.objects if o not in before]
    v = VARIANT if VARIANT != 'lineup' else names.get(os.path.basename(g)[:-4], os.path.basename(g)[:-4])
    if len(glbs) > 1:
        roots = [o for o in new if o.parent is None]
        off = (i - (len(glbs) - 1) / 2) * 0.42
        for r in roots:
            r.location.x += off
            r.location.y += abs(i - (len(glbs) - 1) / 2) * 0.06
            r.rotation_euler.z += math.radians(-12 * (i - (len(glbs) - 1) / 2))
    PARTS.append((v, [o for o in new if o.type == 'MESH']))
bpy.context.view_layer.update()
model = [o for _, objs in PARTS for o in objs]

# ── render settings ──
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.015
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
sc.cycles.max_bounces = 10
sc.cycles.glossy_bounces = 6
sc.cycles.transparent_max_bounces = 8
sc.cycles.caustics_reflective = False
sc.cycles.caustics_refractive = False
sc.cycles.blur_glossy = 0.5
sc.render.film_transparent = False
sc.view_settings.view_transform = 'AgX'
for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
    try:
        sc.view_settings.look = look
        break
    except Exception:
        pass
sc.view_settings.exposure = float(os.environ.get('HM_EXP', '-2.6'))
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_depth = '8'


# ── material helpers ──
def nodes_of(mat):
    return mat.node_tree.nodes, mat.node_tree.links


def principled(mat):
    return next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)


def leather_material():
    """Fine-grain black full-grain leather with a waxed sheen (replaces the viewer's placeholder grain)."""
    m = bpy.data.materials.new('black_leather_cycles')
    m.use_nodes = True
    N, L = nodes_of(m)
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL':
            N.remove(n)
    out = next(n for n in N if n.type == 'OUTPUT_MATERIAL')
    tc = N.new('ShaderNodeTexCoord')
    # big, soft hide variation
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18; nz.inputs['Detail'].default_value = 4
    # pebble grain: voronoi cells ~0.7 mm, distorted by noise for organic shape
    warp = N.new('ShaderNodeTexNoise'); warp.inputs['Scale'].default_value = 300; warp.inputs['Detail'].default_value = 2
    mix = N.new('ShaderNodeVectorMath'); mix.operation = 'MULTIPLY_ADD'
    mix.inputs[1].default_value = (0.0006, 0.0006, 0.0006)
    L.new(warp.outputs['Color'], mix.inputs[0]); L.new(tc.outputs['Object'], mix.inputs[2])
    L.new(tc.outputs['Object'], warp.inputs['Vector'])
    vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 1500
    L.new(mix.outputs[0], vor.inputs['Vector'])
    vor2 = N.new('ShaderNodeTexVoronoi'); vor2.feature = 'DISTANCE_TO_EDGE'; vor2.inputs['Scale'].default_value = 520
    L.new(mix.outputs[0], vor2.inputs['Vector'])
    crease = N.new('ShaderNodeMapRange'); crease.inputs['From Min'].default_value = 0.0; crease.inputs['From Max'].default_value = 0.12
    L.new(vor.outputs['Distance'], crease.inputs['Value'])
    crease2 = N.new('ShaderNodeMapRange'); crease2.inputs['From Min'].default_value = 0.0; crease2.inputs['From Max'].default_value = 0.06
    L.new(vor2.outputs['Distance'], crease2.inputs['Value'])
    hmul = N.new('ShaderNodeMath'); hmul.operation = 'MULTIPLY'
    L.new(crease.outputs['Result'], hmul.inputs[0]); L.new(crease2.outputs['Result'], hmul.inputs[1])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.9; bump.inputs['Distance'].default_value = 0.00025
    L.new(hmul.outputs[0], bump.inputs['Height'])
    # colour: near-black with a warm undertone; creases darker
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.004, 0.0038, 0.0036, 1)
    ramp.color_ramp.elements[1].color = (0.016, 0.0155, 0.015, 1)
    L.new(hmul.outputs[0], ramp.inputs['Fac'])
    tone = N.new('ShaderNodeMixRGB'); tone.blend_type = 'MULTIPLY'; tone.inputs['Fac'].default_value = 0.25
    L.new(ramp.outputs['Color'], tone.inputs['Color1']); L.new(nz.outputs['Color'], tone.inputs['Color2'])
    rough = N.new('ShaderNodeMapRange'); rough.inputs['To Min'].default_value = 0.62; rough.inputs['To Max'].default_value = 0.38
    L.new(hmul.outputs[0], rough.inputs['Value'])
    b = N.new('ShaderNodeBsdfPrincipled')
    L.new(tone.outputs['Color'], b.inputs['Base Color'])
    L.new(rough.outputs['Result'], b.inputs['Roughness'])
    L.new(bump.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Coat Weight'].default_value = 0.12
    b.inputs['Coat Roughness'].default_value = 0.35
    b.inputs['Sheen Weight'].default_value = 0.08
    b.inputs['Sheen Roughness'].default_value = 0.5
    b.inputs['Sheen Tint'].default_value = (0.3, 0.29, 0.28, 1)
    b.inputs['Specular IOR Level'].default_value = 0.45
    L.new(b.outputs[0], out.inputs['Surface'])
    return m


# variant-specific material upgrades
for v, objs in PARTS:
    if v != 'leather':
        continue
    lm = leather_material()
    for o in objs:
        for s in o.material_slots:
            if s.material and s.material.name.startswith('black_tolex'):
                s.material = lm
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    p = principled(mat)
    if not p:
        continue
    n = mat.name
    if n.startswith('ring_led_arc'):
        p.inputs['Emission Strength'].default_value = 14.0
    elif n.startswith(('mat_7', 'mat_8')):  # status LEDs
        p.inputs['Emission Strength'].default_value = 9.0
    elif n.startswith('display_panel'):
        p.inputs['Emission Strength'].default_value = 3.2
    elif n.startswith('thread_'):  # cream waxed saddle thread, as in the design note ("krém varrás")
        p.inputs['Base Color'].default_value = (0.62, 0.52, 0.36, 1)
        p.inputs['Roughness'].default_value = 0.45
        p.inputs['Sheen Weight'].default_value = 0.4
    elif n.startswith('poliigon_steel'):
        p.inputs['Anisotropic'].default_value = max(p.inputs['Anisotropic'].default_value, 0.6)

# ── bounds / centre ──
mn = Vector((1e9,) * 3); mx = -mn
for o in model:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
ctr = (mn + mx) / 2
FLOOR = mn.z

# ── studio: dark sweep floor ──
def sweep():
    import bmesh
    me = bpy.data.meshes.new('sweep'); bm = bmesh.new()
    W, R, back, H = 8.0, 1.2, 2.2, 3.0
    prof = []
    for i in range(10):
        prof.append((-6.0 + i * (6.0 + back - R) / 9, 0.0))
    for i in range(1, 17):
        a = i / 16 * math.pi / 2
        prof.append((back - R + R * math.sin(a), R - R * math.cos(a)))
    prof.append((back, H))
    rows = []
    for x in (-W, W):
        rows.append([bm.verts.new((x, y, z + FLOOR)) for (y, z) in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('sweep', me); sc.collection.objects.link(ob)
    m = bpy.data.materials.new('sweep'); m.use_nodes = True
    b = principled(m)
    b.inputs['Base Color'].default_value = (0.007, 0.007, 0.008, 1)
    b.inputs['Roughness'].default_value = 0.22
    b.inputs['Specular IOR Level'].default_value = 0.35
    ob.data.materials.append(m)
    return ob

sweep_mat = principled(sweep().data.materials[0])

# world: very dark, slight cool tone
world = bpy.data.worlds.new('w'); sc.world = world; world.use_nodes = True
WN, WL = world.node_tree.nodes, world.node_tree.links
bg = WN['Background']; wout = WN['World Output']
bg.inputs['Color'].default_value = (0.004, 0.0045, 0.0055, 1)
studio = WN.new('ShaderNodeBackground')
tcw = WN.new('ShaderNodeTexCoord'); sep = WN.new('ShaderNodeSeparateXYZ')
WL.new(tcw.outputs['Generated'], sep.inputs[0])
ramp = WN.new('ShaderNodeValToRGB')  # by direction z: floor dark, horizon band, bright ceiling
cr = ramp.color_ramp; cr.interpolation = 'EASE'
cr.elements[0].position = 0.45; cr.elements[0].color = (0.004, 0.004, 0.005, 1)
cr.elements[1].position = 1.0; cr.elements[1].color = (0.9, 0.9, 0.92, 1)
e = cr.elements.new(0.52); e.color = (0.35, 0.35, 0.37, 1)
e = cr.elements.new(0.6); e.color = (0.05, 0.05, 0.055, 1)
e = cr.elements.new(0.85); e.color = (0.25, 0.25, 0.26, 1)
zr = WN.new('ShaderNodeMapRange'); zr.inputs['From Min'].default_value = -1.0
WL.new(sep.outputs['Z'], zr.inputs['Value']); WL.new(zr.outputs['Result'], ramp.inputs['Fac'])
WL.new(ramp.outputs['Color'], studio.inputs['Color'])
studio.inputs['Strength'].default_value = float(os.environ.get('HM_ENV', '1.2'))
lp = WN.new('ShaderNodeLightPath'); mixw = WN.new('ShaderNodeMixShader')
WL.new(lp.outputs['Is Camera Ray'], mixw.inputs['Fac'])
WL.new(studio.outputs[0], mixw.inputs[1]); WL.new(bg.outputs[0], mixw.inputs[2])
WL.new(mixw.outputs[0], wout.inputs['Surface'])


def area(name, loc, target, size, power, color=(1, 1, 1), shape='RECTANGLE', size_y=None, glossy=True):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.shape = shape; ld.size = size
    if size_y:
        ld.size_y = size_y
    ld.energy = power; ld.color = color
    ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
    ob.location = Vector(loc)
    d = (Vector(target) - ob.location).normalized()
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    ob.visible_glossy = glossy
    return ob

T = (ctr.x, ctr.y, ctr.z)
LIGHTS = {
    'key': area('key', (-0.9, -0.9, 1.0), T, 1.1, 260, (1.0, 0.97, 0.93), size_y=0.7),
    'top': area('top', (0.0, 0.05, 1.25), T, 1.6, 230, (1.0, 1.0, 1.0), size_y=0.6),
    'fill': area('fill', (1.1, -0.6, 0.45), T, 1.0, 60, (0.92, 0.95, 1.0), size_y=1.0),
    'rimL': area('rimL', (-0.8, 0.9, 0.35), T, 1.2, 160, (0.85, 0.9, 1.0), size_y=0.08),
    'rimR': area('rimR', (0.85, 0.85, 0.4), T, 1.2, 140, (1.0, 0.95, 0.9), size_y=0.08),
    'strip': area('strip', (0.0, -1.3, 0.22), T, 1.8, 35, (1.0, 1.0, 1.0), size_y=0.05),
}
for k, sp in (('key', 70), ('top', 95), ('fill', 90)):
    LIGHTS[k].data.spread = math.radians(sp)  # keep softbox spill off the backdrop
    LIGHTS[k].data.energy *= {'key': 0.38, 'top': 0.42, 'fill': 0.45}[k]  # spread concentrates power
BASE_ENERGY = {k: v.data.energy for k, v in LIGHTS.items()}

# ── camera ──
cam_data = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_data); sc.collection.objects.link(cam)
sc.camera = cam
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt)
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'


def place(az, el, dist, lens, target, w, h, fstop=None, focus=None, shift_y=0.0):
    sc.render.resolution_x = int(w * SCALE); sc.render.resolution_y = int(h * SCALE)
    sc.render.resolution_percentage = 100
    t = Vector(target); tgt.location = t
    a, e = math.radians(az), math.radians(el)
    cam.location = t + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam_data.lens = lens; cam_data.sensor_width = 36; cam_data.shift_y = shift_y
    cam_data.clip_start = 0.005
    if fstop:
        cam_data.dof.use_dof = True; cam_data.dof.aperture_fstop = fstop
        cam_data.dof.focus_distance = focus if focus else (cam.location - t).length
    else:
        cam_data.dof.use_dof = False


def lights(mode):
    for k, ob in LIGHTS.items():
        ob.data.energy = BASE_ENERGY[k]
    if mode == 'dark':  # silhouette: only rims + LEDs
        for k in ('key', 'top', 'fill', 'strip'):
            LIGHTS[k].data.energy = 0.0
        LIGHTS['rimL'].data.energy *= 0.55; LIGHTS['rimR'].data.energy *= 0.55
        sweep_mat.inputs['Base Color'].default_value = (0.002, 0.002, 0.0025, 1)
    else:
        sweep_mat.inputs['Base Color'].default_value = (0.007, 0.007, 0.008, 1)


C = (ctr.x, ctr.y, ctr.z - 0.005)
TOP = (ctr.x - 0.03, ctr.y - 0.012, mx.z - 0.012)
SHOT_DEFS = {
    # name: (az, el, dist, lens, target, w, h, fstop, light mode)
    'hero':     (-38, 20, 1.05, 70, C, 1920, 1080, 8, 'full'),
    'dark':     (-38, 20, 1.05, 70, C, 1920, 1080, 8, 'dark'),
    'orbit':    (38, 20, 1.05, 70, C, 1920, 1080, 8, 'full'),
    'front':    (0, 7, 1.0, 60, (ctr.x, ctr.y, ctr.z - 0.012), 1920, 1080, 9, 'full'),
    'top':      (-18, 50, 0.6, 85, TOP, 1920, 1080, 5.6, 'full'),
    'vertical': (-30, 30, 1.55, 60, C, 1080, 1920, 9, 'full'),
    'square':   (-34, 24, 1.05, 70, C, 1440, 1440, 8, 'full'),
}
# material close-up per variant
SHOT_DEFS['lineup'] = (-6, 17, 2.3, 70, (ctr.x, ctr.y + 0.02, ctr.z - 0.01), 1920, 1080, 11, 'full')
# corner close-up: front-left edge, shows the shell material, seams/stitching, caps and a connector
SHOT_DEFS['macro'] = (-52, 24, 0.40, 100, (mn.x + 0.045, mn.y + 0.035, ctr.z + 0.005), 1920, 1080, 4.5, 'full')

for name in SHOTS:
    az, el, dist, lens, target, w, h, fstop, mode = SHOT_DEFS[name]
    place(az, el, dist, lens, target, w, h, fstop)
    lights(mode)
    sc.render.filepath = os.path.join(OUT, f'{VARIANT}_{name}.png')
    bpy.ops.render.render(write_still=True)
    print('RENDERED', sc.render.filepath, flush=True)
