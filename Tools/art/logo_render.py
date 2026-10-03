"""Blender: render a .claymesh (the logo / icon) front-on with a clay material on a transparent background.
   blender -b --factory-startup --python Tools/art/logo_render.py -- in.claymesh out.png [width] [height] [persp]"""
import math
import os
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../clay"))
argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
W = int(argv[2]) if len(argv) > 2 else 2400
H = int(argv[3]) if len(argv) > 3 else 1300
persp = len(argv) > 4 and argv[4] == "persp"

# reuse the preview reader/material
import importlib.util
spec = importlib.util.spec_from_file_location("pv", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../clay/preview_blender.py"))
sys.argv = [sys.argv[0], "--", os.path.dirname(out)]   # preview_blender parses argv at import; give it a harmless set
pv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pv)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        pass
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.film_transparent = True
sc.render.image_settings.color_mode = "RGBA"
try:
    sc.eevee.taa_render_samples = 96
    sc.eevee.use_raytracing = True
except AttributeError:
    pass
sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = -0.2
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.65, 0.72, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.25

objs = pv.build_object(src, 0.0)
lo, hi = pv.bounds(objs)
ctr = (lo + hi) / 2
size = hi - lo


def light(name, loc, energy, sz, col=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = sz
    ld.color = col
    ob = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = mathutils.Vector(ctr) - mathutils.Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


s = max(size.x, size.z)
light("key", (ctr.x - s * 0.6, ctr.y - s * 1.2, ctr.z + s * 0.9), 80 * s * s, s * 0.8, (1, 0.94, 0.86))
light("fill", (ctr.x + s * 0.9, ctr.y - s * 1.0, ctr.z + s * 0.1), 22 * s * s, s * 1.2, (0.82, 0.9, 1))
light("rim", (ctr.x, ctr.y + s * 1.0, ctr.z + s * 0.8), 70 * s * s, s * 0.8)
cd = bpy.data.cameras.new("cam")
if persp:
    cd.lens = 85
else:
    cd.type = "ORTHO"
    cd.ortho_scale = max(size.x * 1.08, size.z * 1.08 * W / H)
cam = bpy.data.objects.new("cam", cd)
bpy.context.collection.objects.link(cam)
dist = s * 3.2
cam.location = (ctr.x, ctr.y - dist, ctr.z + dist * 0.32)
cam.rotation_euler = (mathutils.Vector(ctr) - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
if persp:
    cd.lens = 85 * (dist / (max(size.x, size.z * W / H) * 1.25)) / (85 / 36)
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
