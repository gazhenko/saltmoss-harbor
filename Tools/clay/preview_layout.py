"""
Saltmoss town previews in Blender (outdoor stage lighting, clay-ish materials, opaque clay sea).

Layout mode — load Game/Assets/Saltmoss/Data/town_layout.json + every model it references + terrain tiles, render an
aerial 3/4 overview and ground-level views from a character's eye height:
  blender -b --factory-startup --python Tools/clay/preview_layout.py -- layout [--out DIR] [--views overview,pier,...]
        [--res 1600] [--night] [--walk]   (--walk also writes a walkability map: reachable walkable cells from spawn)

Models mode — a row of models (Pip for scale) from a few angles:
  blender -b --factory-startup --python Tools/clay/preview_layout.py -- models OUT_PREFIX a.claymesh b.claymesh
        [--views tq,front,back,close] [--res 1100] [--nopip] [--night]
"""
import json
import math
import os
import struct
import sys

import bpy
import mathutils
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
MODELS = os.path.join(ROOT, "Game/Assets/Saltmoss/Models")
LAYOUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Data/town_layout.json")
PIP = os.path.join(MODELS, "chars/pip.claymesh")

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
mode = argv[0] if argv else "layout"
pos_args, opts = [], {}
i = 1
while i < len(argv):
    a = argv[i]
    if a.startswith("--"):
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            opts[a[2:]] = argv[i + 1]
            i += 2
        else:
            opts[a[2:]] = True
            i += 1
    else:
        pos_args.append(a)
        i += 1
NIGHT = bool(opts.get("night"))


# ----------------------------------------------------------------------------------------------------------------
# claymesh -> blender mesh

def read_claymesh(path):
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

    rd("<I")
    (nb,) = rd("<I")
    for _ in range(nb):
        rs()
        rd("<i3f")
    (npc,) = rd("<I")
    pieces = []
    for _ in range(npc):
        name = rs()
        mat, flags, rb = rd("<BBi")
        vc, ic = rd("<II")
        v = np.frombuffer(data, "<f4", vc * 3, o).reshape(-1, 3); o += vc * 12
        n = np.frombuffer(data, "<f4", vc * 3, o).reshape(-1, 3); o += vc * 12
        c = np.frombuffer(data, np.uint8, vc * 4, o).reshape(-1, 4); o += vc * 4
        if flags & 2:
            o += vc * 20
        f = np.frombuffer(data, "<u4", ic, o).reshape(-1, 3); o += ic * 4
        pieces.append(dict(name=name, mat=mat, hidden=bool(flags & 1), v=v, n=n, c=c, f=f))
    (ns,) = rd("<I")
    sockets = []
    for _ in range(ns):
        name = rs()
        vals = rd("<i3f4f")
        sockets.append((name, vals[1:4]))
    return pieces, sockets


_mats = {}


def material(mat_class):
    if mat_class in _mats:
        return _mats[mat_class]
    m = bpy.data.materials.new(f"clay{mat_class}")
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.66
    mr.inputs["To Max"].default_value = 0.14
    links.new(attr.outputs["Alpha"], mr.inputs["Value"])
    links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
    try:
        bsdf.inputs["Subsurface Weight"].default_value = 0.1
        bsdf.inputs["Subsurface Radius"].default_value = (0.02, 0.01, 0.006)
        bsdf.inputs["Specular IOR Level"].default_value = 0.4
    except KeyError:
        pass
    tc = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 6.0
    links.new(tc.outputs["Object"], noise.inputs["Vector"])
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.inputs["Scale"].default_value = 7.0
    wave.inputs["Distortion"].default_value = 8.0
    links.new(tc.outputs["Object"], wave.inputs["Vector"])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    links.new(wave.outputs["Fac"], mul.inputs[0])
    links.new(noise.outputs["Fac"], mul.inputs[1])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.004
    links.new(mul.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if mat_class == 1:
        links.new(attr.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 6.0 if NIGHT else 0.25
    if mat_class == 2:  # cotton wool
        bsdf.inputs["Roughness"].default_value = 1.0
        try:
            bsdf.inputs["Sheen Weight"].default_value = 1.0
            bsdf.inputs["Subsurface Weight"].default_value = 0.35
        except KeyError:
            pass
    if mat_class == 4:  # net: diamond cutout like the Unity shader (14 cells / m)
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(tc.outputs["Object"], sep.inputs[0])

        def mathn(op, a, b=None, val=None):
            n = nodes.new("ShaderNodeMath")
            n.operation = op
            links.new(a, n.inputs[0]) if not isinstance(a, float) else None
            if isinstance(a, float):
                n.inputs[0].default_value = a
            if b is not None:
                if isinstance(b, float):
                    n.inputs[1].default_value = b
                else:
                    links.new(b, n.inputs[1])
            return n.outputs[0]
        u = mathn("MULTIPLY", mathn("ADD", sep.outputs[0], sep.outputs[1]), 14.0)
        v = mathn("MULTIPLY", mathn("ADD", sep.outputs[2], sep.outputs[1]), 14.0)
        s1 = mathn("ABSOLUTE", mathn("SUBTRACT", mathn("FRACT", mathn("ADD", u, v)), 0.5))
        s2 = mathn("ABSOLUTE", mathn("SUBTRACT", mathn("FRACT", mathn("SUBTRACT", u, v)), 0.5))
        mx = mathn("MAXIMUM", s1, s2)
        alpha = mathn("GREATER_THAN", mx, 0.38)
        links.new(alpha, bsdf.inputs["Alpha"])
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
        m.use_backface_culling = False
    _mats[mat_class] = m
    return m


_mesh_cache = {}


def load_meshes(path, show=(), hide=()):
    """-> list of (mesh datablock, name) for the visible pieces (cached per path)."""
    key = (path, tuple(show), tuple(hide))
    if key in _mesh_cache:
        return _mesh_cache[key]
    pieces, sockets = read_claymesh(path)
    base = os.path.splitext(os.path.basename(path))[0]
    out = []
    for p in pieces:
        if (p["hidden"] and p["name"] not in show) or p["name"] in hide:
            continue
        v = p["v"][:, [0, 2, 1]].astype(np.float32)
        f = p["f"][:, [0, 2, 1]].astype(np.int32)
        me = bpy.data.meshes.new(f"{base}_{p['name']}")
        me.vertices.add(len(v))
        me.vertices.foreach_set("co", v.ravel())
        me.loops.add(f.size)
        me.loops.foreach_set("vertex_index", f.ravel())
        me.polygons.add(len(f))
        me.polygons.foreach_set("loop_start", np.arange(0, f.size, 3, dtype=np.int32))
        me.polygons.foreach_set("loop_total", np.full(len(f), 3, np.int32))
        me.update(calc_edges=True)
        col = me.color_attributes.new("Col", "BYTE_COLOR", "POINT")
        c = (p["c"].astype(np.float32) / 255.0).ravel()
        col.data.foreach_set("color_srgb", c)
        me.polygons.foreach_set("use_smooth", np.ones(len(f), bool))
        try:
            me.normals_split_custom_set_from_vertices([tuple(x) for x in p["n"][:, [0, 2, 1]]])
        except Exception:
            pass
        me.materials.append(material(p["mat"]))
        out.append(me)
    _mesh_cache[key] = (out, sockets)
    return out, sockets


def place(path, pos=(0, 0, 0), yaw=0.0, scale=1.0, name=None, show=(), hide=()):
    meshes, sockets = load_meshes(path, show, hide)
    objs = []
    for me in meshes:
        ob = bpy.data.objects.new(name or me.name, me)
        bpy.context.collection.objects.link(ob)
        ob.location = (pos[0], pos[2], pos[1])
        ob.rotation_euler = (0, 0, -math.radians(yaw))
        ob.scale = (scale, scale, scale)
        objs.append(ob)
    return objs


# ----------------------------------------------------------------------------------------------------------------
# stage

def setup_scene(res_x, res_y):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = res_x, res_y
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Base Contrast"
    except Exception:
        pass
    ee = sc.eevee
    for k, v in (("use_raytracing", True), ("taa_render_samples", 40), ("use_shadows", True), ("shadow_ray_count", 2),
                 ("fast_gi_method", "GLOBAL_ILLUMINATION"), ("use_fast_gi", True)):
        try:
            setattr(ee, k, v)
        except Exception:
            pass
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    if NIGHT:
        bg.inputs[0].default_value = (0.05, 0.07, 0.13, 1)
        bg.inputs[1].default_value = 0.6
    else:
        sky = w.node_tree.nodes.new("ShaderNodeTexSky")
        try:
            sky.sky_type = "HOSEK_WILKIE"
        except Exception:
            pass
        try:
            sky.sun_elevation = math.radians(28)
            sky.sun_rotation = math.radians(150)
            sky.turbidity = 5.0
        except Exception:
            pass
        mixn = w.node_tree.nodes.new("ShaderNodeMix")
        mixn.data_type = "RGBA"
        mixn.inputs["Factor"].default_value = 0.55
        mixn.inputs["B"].default_value = (0.62, 0.7, 0.78, 1)
        w.node_tree.links.new(sky.outputs[0], mixn.inputs["A"])
        w.node_tree.links.new(mixn.outputs["Result"], bg.inputs[0])
        bg.inputs[1].default_value = 0.55
    return sc


def sun(elev=34, azim=145, energy=3.6, color=(1.0, 0.9, 0.78), angle=4.0):
    ld = bpy.data.lights.new("sun", "SUN")
    ld.energy = energy * (0.06 if NIGHT else 1.0)
    ld.color = color if not NIGHT else (0.6, 0.7, 1.0)
    ld.angle = math.radians(angle)
    ob = bpy.data.objects.new("sun", ld)
    bpy.context.collection.objects.link(ob)
    # blender: sun points down -Z of the object
    e, a = math.radians(elev), math.radians(azim)
    d = mathutils.Vector((math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)))
    ob.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return ob


def point_light(pos_u, energy=60, color=(1.0, 0.72, 0.4), radius=0.1):
    ld = bpy.data.lights.new("pl", "POINT")
    ld.energy = energy
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new("pl", ld)
    bpy.context.collection.objects.link(ob)
    ob.location = (pos_u[0], pos_u[2], pos_u[1])


def sea_plane(size=900, y=0.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, y))
    ob = bpy.context.active_object
    m = bpy.data.materials.new("sea")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.11, 0.2, 0.23, 1)
    b.inputs["Roughness"].default_value = 0.22
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.35
    nz.inputs["Detail"].default_value = 4
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.35
    bp.inputs["Distance"].default_value = 0.6
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    ob.data.materials.append(m)
    return ob


def table(size, z):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    card = bpy.context.active_object
    cm = bpy.data.materials.new("card")
    cm.use_nodes = True
    cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.34, 0.31, 1)
    cm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    card.data.materials.append(cm)


def camera(sc, loc_u, target_u, lens=35.0, name="cam"):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.1
    cd.clip_end = 2000
    cam = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(cam)
    loc = mathutils.Vector((loc_u[0], loc_u[2], loc_u[1]))
    tgt = mathutils.Vector((target_u[0], target_u[2], target_u[1]))
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    return cam


def bounds(objs):
    bpy.context.view_layer.update()
    lo = np.array([1e9] * 3)
    hi = -lo
    for ob in objs:
        M = np.array(ob.matrix_world)
        co = np.empty(len(ob.data.vertices) * 3, np.float32)
        ob.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        w = co @ M[:3, :3].T + M[:3, 3]
        lo = np.minimum(lo, w.min(0))
        hi = np.maximum(hi, w.max(0))
    return lo, hi  # blender coords


def render(sc, path):
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("[render]", path)


# ----------------------------------------------------------------------------------------------------------------
# models mode

def models_mode():
    prefix = pos_args[0]
    files = pos_args[1:]
    res = int(opts.get("res", 1100))
    views = str(opts.get("views", "tq,front,back")).split(",")
    sc = setup_scene(res, int(res * 0.62))
    sun()
    objs_all = []
    x = 0.0
    if not opts.get("nopip"):
        files = files + [PIP]
    gap = float(opts.get("gap", 0.6))
    for f in files:
        o = place(f)
        lo, hi = bounds(o)
        for ob in o:
            ob.location.x += x - lo[0]
        x += (hi[0] - lo[0]) + gap
        objs_all += o
    lo, hi = bounds(objs_all)
    ctr = (lo + hi) / 2
    for ob in objs_all:
        ob.location.x -= ctr[0]
        ob.location.y -= ctr[1]
    lo, hi = bounds(objs_all)
    ctr = (lo + hi) / 2
    size = float(max(hi - lo))
    table(size * 30, lo[2] - 0.002)
    if NIGHT:
        for f in files:
            pass
    for v in views:
        az, el, distf, lens = {"tq": (35, 18, 1.0, 50), "front": (0, 8, 1.0, 50), "back": (180, 14, 1.0, 50), "side": (90, 10, 1.0, 50),
                               "left": (-50, 16, 1.0, 50), "top": (20, 60, 1.0, 50), "close": (25, 10, 0.45, 50), "low": (30, 3, 0.6, 35)}.get(v, (35, 18, 1.0, 50))
        a, e = math.radians(az), math.radians(el)
        fov = 2 * math.atan(36 / 2 / lens)
        ext = hi - lo
        # projected extent: horizontal span seen from this azimuth, and height
        span = abs(ext[0] * math.cos(a)) + abs(ext[1] * math.sin(a))
        vert = ext[2] * math.cos(e) + (abs(ext[1] * math.cos(a)) + abs(ext[0] * math.sin(a))) * math.sin(e)
        aspect = sc.render.resolution_x / sc.render.resolution_y
        dist = max(span / aspect, vert) / (2 * math.tan(fov / 2)) * 1.12 * distf + (abs(ext[1] * math.cos(a)) + abs(ext[0] * math.sin(a))) * 0.5
        tgt = mathutils.Vector((ctr[0], ctr[1], lo[2] + ext[2] * 0.45))
        if v == "close":
            tgt = mathutils.Vector((ctr[0] - ext[0] * 0.2, ctr[1], lo[2] + ext[2] * 0.55))
        pos = tgt + mathutils.Vector((dist * math.sin(a) * math.cos(e), dist * math.cos(a) * math.cos(e), dist * math.sin(e)))
        cd = bpy.data.cameras.new("c")
        cd.lens = lens
        cd.clip_end = 5000
        cam = bpy.data.objects.new("c", cd)
        bpy.context.collection.objects.link(cam)
        cam.location = pos
        cam.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        render(sc, f"{prefix}_{v}.png")


# ----------------------------------------------------------------------------------------------------------------
# layout mode

# camera views (Unity coords): eye, target, lens(mm). Ground views are at a critter's eye (~1.6 m) or a third-person
# camera (6-10 m behind, a few metres up).
VIEWS = {
    "overview": dict(eye=(62, 48, 102), target=(2, 1, -6), lens=28),
    "harbor": dict(eye=(-26, 22, 58), target=(6, 2, -2), lens=32),
    "pier": dict(eye=(0.4, 3.4, 15.0), target=(-4.5, 2.6, -1.0), lens=30),
    "street": dict(eye=(-12.5, 3.3, -12.0), target=(10.0, 2.6, -8.0), lens=30),
    "tps": dict(eye=(15.5, 5.2, -15.5), target=(17.5, 2.4, 3.0), lens=32),
    "beach": dict(eye=(-20.5, 3.6, -4.0), target=(-32.0, 2.2, 7.5), lens=30),
    "slope": dict(eye=(-2.0, 5.5, -10.0), target=(0.0, 4.0, -30.0), lens=30),
    "sea": dict(eye=(10.0, 4.0, 62.0), target=(2.0, 3.0, 0.0), lens=32),
    # density pass: plan view, the hillside village, the boat's view entering the harbour, and third-person views
    # (camera 6-10 m behind the player and a few metres above, as in game) on the street, lanes, stairs and walks
    "top": dict(eye=(4.0, 120.0, -4.5), target=(4.0, 0.0, -4.0), lens=35),
    "village": dict(eye=(2.0, 9.0, 22.0), target=(2.0, 4.0, -24.0), lens=30),
    "boat_entry": dict(eye=(1.5, 7.5, 70.0), target=(2.0, 3.5, 0.0), lens=32),
    "boat_mid": dict(eye=(5.0, 6.0, 46.0), target=(0.0, 3.5, -8.0), lens=32),
    "tps_street": dict(eye=(3.0, 5.6, -5.5), target=(0.0, 4.0, -26.0), lens=32),
    "tps_hill": dict(eye=(8.5, 9.8, -27.0), target=(-6.0, 6.6, -31.5), lens=32),
    "tps_westwalk": dict(eye=(-14.6, 5.6, -11.5), target=(-16.5, 2.6, 8.0), lens=32),
    "tps_stairs": dict(eye=(11.5, 11.2, -29.5), target=(8.5, 9.5, -46.0), lens=32),
    "tps_cove": dict(eye=(11.5, 5.4, 2.5), target=(30.0, 2.6, 2.0), lens=32),
    "tps_beach": dict(eye=(-50.0, 6.6, 9.0), target=(-38.0, 1.2, 15.5), lens=32),
    "westcove": dict(eye=(-6.0, 4.5, 24.0), target=(-20.0, 1.5, 4.0), lens=32),
}


def model_path(mid):
    return os.path.join(MODELS, mid + ".claymesh")


def layout_mode():
    out = opts.get("out", os.path.join(HERE, "previews"))
    os.makedirs(out, exist_ok=True)
    res = int(opts.get("res", 1600))
    lay = json.load(open(opts.get("layout", LAYOUT)))
    sc = setup_scene(res, int(res * 0.5625))
    sun()
    sea_plane()
    # terrain
    tdir = os.path.join(MODELS, "terrain")
    if os.path.isdir(tdir):
        for f in sorted(os.listdir(tdir)):
            if f.endswith(".claymesh"):
                place(os.path.join(tdir, f))
    missing = set()
    for inst in lay["instances"]:
        p = model_path(inst["model"])
        if not os.path.exists(p):
            missing.add(inst["model"])
            continue
        place(p, inst["pos"], inst.get("yaw", 0.0), inst.get("scale", 1.0))
    if missing:
        print("[layout] missing models:", sorted(missing))
    A = lay.get("anchors", {})
    # characters for scale at a few anchors
    for k in ("player_spawn", "shop_counter", "walter_post", "nell_post", "marge_post", "inkwell_post", "shelby_post"):
        if k in A and os.path.exists(PIP):
            place(PIP, A[k]["pos"], A[k].get("yaw", 0.0))
    for q in A.get("queue", [])[:3]:
        place(PIP, q, 0.0, 0.9)
    if NIGHT:
        for p in A.get("lantern_lights", []):
            point_light(p, 40)
        for p in A.get("window_lights", []):
            point_light(p, 25, (1.0, 0.75, 0.45), 0.3)
        if "lighthouse_lamp" in A:
            point_light(A["lighthouse_lamp"]["pos"] if isinstance(A["lighthouse_lamp"], dict) else A["lighthouse_lamp"], 3000, (1, 0.85, 0.6), 0.5)
    views = VIEWS
    want = str(opts.get("views", ",".join(views.keys()))).split(",")
    for name in want:
        if name not in views:
            continue
        v = views[name]
        camera(sc, v["eye"], v["target"], v.get("lens", 35))
        render(sc, os.path.join(out, f"layout_{name}{'_night' if NIGHT else ''}.png"))


if mode == "models":
    models_mode()
else:
    layout_mode()
