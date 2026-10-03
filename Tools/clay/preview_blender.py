"""
Render .claymesh files in Blender with a clay look-alike material, studio lights and a tabletop card.

  blender -b --factory-startup --python Tools/clay/preview_blender.py -- OUT_DIR file1.claymesh [file2 ...]
        [--views threequarter,front,side,back] [--res 640] [--show a,b] [--hide a,b] [--pose name=xdeg,ydeg,zdeg;...]
        [--row]   (lay several models out side by side in one shot instead of rendering each separately)

Writes OUT_DIR/<model>_<view>.png. Used by Tools/clay/preview.py which also builds contact sheets.
"""
import math
import os
import struct
import sys

import bpy
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
out_dir = argv[0]
files, opts = [], {}
i = 1
while i < len(argv):
    a = argv[i]
    if a.startswith("--"):
        if a in ("--row",):
            opts[a[2:]] = True
            i += 1
        else:
            opts[a[2:]] = argv[i + 1]
            i += 2
    else:
        files.append(a)
        i += 1
views = opts.get("views", "threequarter,front,side,back").split(",")
res = int(opts.get("res", 640))
show = set(filter(None, opts.get("show", "").split(",")))
hide = set(filter(None, opts.get("hide", "").split(",")))
os.makedirs(out_dir, exist_ok=True)


def read(path):
    data = open(path, "rb").read()
    o = 4

    def rd(fmt):
        nonlocal o
        v = struct.unpack_from(fmt, data, o)
        o += struct.calcsize(fmt)
        return v

    def rs():
        nonlocal o
        (n,) = rd("<H")
        s = data[o:o + n].decode()
        o += n
        return s

    (ver,) = rd("<I")
    (nb,) = rd("<I")
    bones = []
    for _ in range(nb):
        name = rs()
        p, x, y, z = rd("<i3f")
        bones.append((name, p, (x, y, z)))
    (npc,) = rd("<I")
    pieces = []
    for _ in range(npc):
        name = rs()
        mat, flags, rb = rd("<BBi")
        vc, ic = rd("<II")
        v = struct.unpack_from(f"<{vc * 3}f", data, o); o += vc * 12
        n = struct.unpack_from(f"<{vc * 3}f", data, o); o += vc * 12
        c = data[o:o + vc * 4]; o += vc * 4
        if flags & 2:
            o += vc * 4 + vc * 16
        f = struct.unpack_from(f"<{ic}I", data, o); o += ic * 4
        pieces.append(dict(name=name, mat=mat, hidden=bool(flags & 1), v=v, n=n, c=c, f=f))
    return bones, pieces


def clay_material(name, mat_class):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(attr.outputs["Alpha"], sep.inputs[0])
    # roughness from gloss (alpha)
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.62
    mr.inputs["To Max"].default_value = 0.12
    links.new(attr.outputs["Alpha"], mr.inputs["Value"])
    links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
    try:
        bsdf.inputs["Subsurface Weight"].default_value = 0.12
        bsdf.inputs["Subsurface Radius"].default_value = (0.02, 0.01, 0.006)
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
    except KeyError:
        pass
    # fingerprint-ish micro detail
    tc = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.inputs["Scale"].default_value = 60.0
    wave.inputs["Distortion"].default_value = 6.0
    links.new(tc.outputs["Object"], wave.inputs["Vector"])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18.0
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    mixb = nodes.new("ShaderNodeMath")
    mixb.operation = "MULTIPLY"
    links.new(wave.outputs["Fac"], mixb.inputs[0])
    links.new(noise.outputs["Fac"], mixb.inputs[1])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.002
    links.new(mixb.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if mat_class == 1:
        try:
            links.new(attr.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = 2.0
        except KeyError:
            pass
    return m


def build_object(path, offset):
    bones, pieces = read(path)
    base = os.path.splitext(os.path.basename(path))[0]
    mats = {}
    objs = []
    for p in pieces:
        visible = (not p["hidden"] or p["name"] in show) and p["name"] not in hide
        if not visible:
            continue
        vc = len(p["v"]) // 3
        # Unity (x right, y up, z fwd, left-handed) -> Blender (x right, y fwd... ) : (x, z, y) and flip winding
        verts = [(p["v"][3 * k] + offset, p["v"][3 * k + 2], p["v"][3 * k + 1]) for k in range(vc)]
        faces = [(p["f"][3 * k], p["f"][3 * k + 2], p["f"][3 * k + 1]) for k in range(len(p["f"]) // 3)]
        me = bpy.data.meshes.new(f"{base}_{p['name']}")
        me.from_pydata(verts, [], faces)
        me.update()
        col = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
        c = p["c"]
        cols = []
        for k in range(vc):
            cols.extend((c[4 * k] / 255.0, c[4 * k + 1] / 255.0, c[4 * k + 2] / 255.0, c[4 * k + 3] / 255.0))
        # BYTE_COLOR stores sRGB; foreach_set takes linear floats via .color_srgb
        col.data.foreach_set("color_srgb", cols)
        normals = [(p["n"][3 * k], p["n"][3 * k + 2], p["n"][3 * k + 1]) for k in range(vc)]
        try:
            me.normals_split_custom_set_from_vertices(normals)
        except Exception:
            pass
        for poly in me.polygons:
            poly.use_smooth = True
        key = p["mat"]
        if key not in mats:
            mats[key] = clay_material(f"clay{key}", key)
        me.materials.append(mats[key])
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.collection.objects.link(ob)
        objs.append(ob)
    return objs


def bounds(objs):
    lo = mathutils.Vector((1e9, 1e9, 1e9))
    hi = -lo
    for ob in objs:
        for v in ob.data.vertices:
            w = ob.matrix_world @ v.co
            lo = mathutils.Vector(map(min, lo, w))
            hi = mathutils.Vector(map(max, hi, w))
    return lo, hi


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    try:
        sc.eevee.use_raytracing = True
        sc.eevee.taa_render_samples = 48
    except AttributeError:
        pass
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.6, 0.66, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.35
    return sc


def add_light(name, kind, loc, energy, size, color=(1, 1, 1), target=(0, 0, 0.5)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = mathutils.Vector(target) - mathutils.Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def render_set(paths, tag):
    sc = setup_scene()
    objs = []
    x = 0.0
    sizes = []
    for p in paths:
        o = build_object(p, 0.0)
        lo, hi = bounds(o)
        wdt = hi.x - lo.x
        for ob in o:
            ob.location.x += x - lo.x
        x += wdt + max(0.08, wdt * 0.25)
        objs += o
        sizes.append(wdt)
    lo, hi = bounds(objs)
    ctr = (lo + hi) / 2
    for ob in objs:
        ob.location.x -= ctr.x
        ob.location.y -= ctr.y
    lo, hi = bounds(objs)
    ctr = (lo + hi) / 2
    size = max(hi - lo)
    # tabletop card
    bpy.ops.mesh.primitive_plane_add(size=size * 8, location=(0, 0, lo.z))
    card = bpy.context.active_object
    cm = bpy.data.materials.new("card")
    cm.use_nodes = True
    cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.4, 0.37, 1)
    cm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    card.data.materials.append(cm)
    s = size
    add_light("key", "AREA", (s * 1.6, s * 1.8, ctr.z + s * 1.6), 220 * s * s, s * 1.2, (1.0, 0.93, 0.84), tuple(ctr))
    add_light("fill", "AREA", (-s * 2.0, s * 1.2, ctr.z + s * 0.6), 70 * s * s, s * 2.0, (0.8, 0.88, 1.0), tuple(ctr))
    add_light("rim", "AREA", (-s * 0.6, -s * 2.0, ctr.z + s * 1.4), 160 * s * s, s * 0.8, (0.9, 0.95, 1.0), tuple(ctr))
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 70
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x = int(res * (max(1.0, (hi.x - lo.x) / max(hi.z - lo.z, 1e-3)) if opts.get("row") else 1.0))
    out = []
    for v in views:
        az = {"front": 0, "threequarter": 35, "side": 90, "back": 180, "top": 0, "left": -60}.get(v, 35)
        el = 55 if v == "top" else 12
        dist = size * 3.1
        a, e = math.radians(az), math.radians(el)
        pos = mathutils.Vector((ctr.x + dist * math.sin(a) * math.cos(e), ctr.y + dist * math.cos(a) * math.cos(e), ctr.z + dist * math.sin(e)))  # models face +Y here
        cam.location = pos
        cam.rotation_euler = (mathutils.Vector(ctr) - pos).to_track_quat("-Z", "Y").to_euler()
        f = os.path.join(out_dir, f"{tag}_{v}.png")
        sc.render.filepath = f
        bpy.ops.render.render(write_still=True)
        out.append(f)
    return out


if opts.get("row"):
    render_set(files, opts.get("tag", "row"))
else:
    for fpath in files:
        render_set([fpath], os.path.splitext(os.path.basename(fpath))[0])
