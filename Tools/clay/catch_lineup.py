"""
Contact sheets / line-ups for the catch (no rebuild): lays existing .claymesh files out in a labelled grid on a
tabletop and renders one image with Blender, reusing preview_blender's clay material and lights.

  Tools/.venv/bin/python Tools/clay/catch_lineup.py fish --tag fish_lineup [--cols 4] [--yaw 90] [--real] [--el 28]
  Tools/.venv/bin/python Tools/clay/catch_lineup.py treasure/ship_bell treasure/pearl --tag t1

Arguments are groups (every .claymesh in Models/<group>/) or group/id. --yaw rotates every model about the vertical
(90 = a fish's head points to image right, showing its +X flank). --real keeps true relative sizes.
Writes Tools/clay/previews/<tag>.jpg.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
MODELS = os.path.join(ROOT, "Game/Assets/Saltmoss/Models")
PREVIEWS = os.path.join(HERE, "previews")


def cli():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("items", nargs="+")
    ap.add_argument("--tag", default="lineup")
    ap.add_argument("--cols", type=int, default=0)
    ap.add_argument("--yaw", type=float, default=0.0)
    ap.add_argument("--el", type=float, default=24.0)
    ap.add_argument("--az", type=float, default=0.0)
    ap.add_argument("--cell", type=int, default=420)
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--nolabel", action="store_true")
    a = ap.parse_args()
    paths = []
    for it in a.items:
        yaw = ""
        if "@" in it:
            it, yaw = it.split("@")
            yaw = "@" + yaw
        d = os.path.join(MODELS, it)
        if os.path.isdir(d):
            paths += sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".claymesh"))
        else:
            p = os.path.join(MODELS, it + ".claymesh")
            if os.path.exists(p):
                paths.append(p + yaw)
            else:
                print("missing", it)
    if not paths:
        return
    os.makedirs(PREVIEWS, exist_ok=True)
    out = os.path.join(PREVIEWS, a.tag + ".png")
    cmd = ["blender", "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--", out, str(a.cols), str(a.yaw),
           str(a.el), str(a.az), str(a.cell), "1" if a.real else "0", "0" if a.nolabel else "1", *paths]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        print(r.stdout[-3000:], r.stderr[-3000:])
        return
    from PIL import Image
    jpg = os.path.join(PREVIEWS, a.tag + ".jpg")
    Image.open(out).convert("RGB").save(jpg, quality=88)
    os.remove(out)
    print("[lineup]", jpg)


def glass_mat():
    """Transparent tinted glass for pieces named *glass_clear* (Unity should give them a transparent material)."""
    import bpy
    m = bpy.data.materials.get("glass_clear")
    if m:
        return m
    m = bpy.data.materials.new("glass_clear")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], b.inputs["Base Color"])
    for k, v in (("Transmission Weight", 0.92), ("Roughness", 0.06), ("IOR", 1.45), ("Alpha", 1.0)):
        try:
            b.inputs[k].default_value = v
        except KeyError:
            pass
    try:
        m.surface_render_method = "DITHERED"
        m.use_raytrace_refraction = True
    except AttributeError:
        pass
    return m


def blender_main():
    import math
    import bpy
    import mathutils
    argv = sys.argv[sys.argv.index("--") + 1:]
    out, cols, yaw, el, az, cell, real, label = argv[:8]
    files = argv[8:]
    cols, yaw, el, az, cell, real, label = int(cols), float(yaw), float(el), float(az), int(cell), real == "1", label == "1"
    # import the stock preview module for its material/scene helpers (with no files it renders nothing)
    sys.argv = [sys.argv[0], "--", os.path.dirname(out)]
    sys.path.insert(0, HERE)
    import preview_blender as pb
    pb.setup_scene()
    n = len(files)
    if cols <= 0:
        cols = max(1, min(6, int(math.ceil(math.sqrt(n * 1.6)))))
    rows = int(math.ceil(n / cols))
    groups = []
    for f in files:
        fyaw = yaw
        if "@" in f:
            f, fy = f.split("@")
            fyaw = float(fy)
        objs = pb.build_object(f, 0.0)
        for ob in objs:
            if "glass_clear" in ob.name:
                ob.data.materials.clear()
                ob.data.materials.append(glass_mat())
            ob.rotation_euler = (0, 0, math.radians(fyaw))
        bpy.context.view_layer.update()
        lo, hi = pb.bounds(objs)
        groups.append((f, objs, lo, hi))
    sizes = [max(hi - lo) for _, _, lo, hi in groups]
    big = max(sizes)
    scales = [1.0 / big for _ in sizes] if real else [1.0 / s for s in sizes]
    e = math.radians(el)
    dims = [((hi - lo) * s) for (_, _, lo, hi), s in zip(groups, scales)]
    lab = 0.13 if label else 0.0
    cw = max(d.x for d in dims) * 1.1 + 0.06
    ph = max(d.z * math.cos(e) + d.y * math.sin(e) for d in dims) + lab
    ch = max(max(d.y for d in dims) + lab + 0.1, ph * 1.06 / max(math.sin(e), 0.05))
    for i, (f, objs, lo, hi) in enumerate(groups):
        s = scales[i]
        r, c = divmod(i, cols)
        cx = (c - (cols - 1) / 2) * cw
        cy = ((rows - 1) / 2 - r) * ch
        ctr = (lo + hi) / 2
        for ob in objs:
            ob.scale = (s, s, s)
            ob.location = (cx - ctr.x * s, cy - ctr.y * s, -lo.z * s)
        if label:
            cu = bpy.data.curves.new("lbl", "FONT")
            cu.body = os.path.splitext(os.path.basename(f))[0]
            cu.size = 0.075
            cu.align_x = "CENTER"
            tob = bpy.data.objects.new("lbl", cu)
            bpy.context.collection.objects.link(tob)
            tob.location = (cx, cy - dims[i].y / 2 - 0.05, 0.0)
            tob.rotation_euler = (math.radians(90) - e, 0, 0)
            m = bpy.data.materials.new("lblm")
            m.use_nodes = True
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
            cu.materials.append(m)
    bpy.context.view_layer.update()
    W = cols * cw
    H = rows * ch
    bpy.ops.mesh.primitive_plane_add(size=max(W, H) * 8, location=(0, 0, 0))
    card = bpy.context.active_object
    cm = bpy.data.materials.new("card")
    cm.use_nodes = True
    cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.24, 0.225, 0.205, 1)
    cm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    card.data.materials.append(cm)
    s = max(W, H, 1.0)
    ctr = (0, 0, 0.3)
    pb.add_light("key", "AREA", (s * 0.9, -s * 1.1, s * 1.3), 70 * s * s, s * 0.9, (1.0, 0.93, 0.84), ctr)
    pb.add_light("fill", "AREA", (-s * 1.2, -s * 0.8, s * 0.6), 22 * s * s, s * 1.6, (0.8, 0.88, 1.0), ctr)
    pb.add_light("rim", "AREA", (-s * 0.3, s * 1.3, s * 1.0), 60 * s * s, s * 0.7, (0.9, 0.95, 1.0), ctr)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_d)
    bpy.context.collection.objects.link(cam)
    sc = bpy.context.scene
    sc.camera = cam
    a = math.radians(az)
    fwd = mathutils.Vector((-math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), -math.sin(e)))
    right = fwd.cross(mathutils.Vector((0, 0, 1))).normalized()
    up = right.cross(fwd).normalized()
    pts = []
    for ob in bpy.context.scene.objects:
        if ob.type in ("MESH", "FONT") and ob is not card:
            for corner in ob.bound_box:
                pts.append(ob.matrix_world @ mathutils.Vector(corner))
    xs = [p.dot(right) for p in pts]
    ys = [p.dot(up) for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mx, my = (x1 - x0) * 0.03 + 0.03, (y1 - y0) * 0.03 + 0.03
    x0, x1, y0, y1 = x0 - mx, x1 + mx, y0 - my, y1 + my
    centre = right * (x0 + x1) / 2 + up * (y0 + y1) / 2
    cam.location = centre - fwd * s * 6
    cam.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
    aspect = (y1 - y0) / (x1 - x0)
    sc.render.resolution_x = int(cols * cell)
    sc.render.resolution_y = max(64, int(cols * cell * aspect))
    cam_d.ortho_scale = max(x1 - x0, y1 - y0)
    cam_d.clip_end = s * 20
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    if "--" in sys.argv and any("blender" in a.lower() for a in sys.argv[:1]) or "bpy" in sys.modules:
        blender_main()
    else:
        try:
            import bpy  # noqa: F401
            blender_main()
        except ImportError:
            cli()
