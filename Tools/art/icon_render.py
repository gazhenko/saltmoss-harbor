"""Blender: the app icon — Pip's clay bust in front of a round sea-teal clay tile.
   blender -b --factory-startup --python Tools/art/icon_render.py -- pip.claymesh out.png"""
import math
import os
import sys

import bpy
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
import importlib.util
spec = importlib.util.spec_from_file_location("pv", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../clay/preview_blender.py"))
sys.argv = [sys.argv[0], "--", os.path.dirname(out)]
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
sc.render.resolution_x = sc.render.resolution_y = 1024
sc.render.film_transparent = True
sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = -0.1
try:
    sc.eevee.taa_render_samples = 96
    sc.eevee.use_raytracing = True
except AttributeError:
    pass
w = bpy.data.worlds.new("w")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.6, 0.65, 0.72, 1)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.3

objs = pv.build_object(src, 0.0)
lo, hi = pv.bounds(objs)
height = hi.z - lo.z
head = mathutils.Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z + height * 0.7))

# clay tile behind
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=height * 0.4, depth=0.05, location=(head.x, head.y - 0.3, head.z - height * 0.02), rotation=(math.radians(90), 0, 0))
tile = bpy.context.active_object
bpy.ops.object.modifier_add(type="BEVEL")
tile.modifiers["Bevel"].width = 0.02
tile.modifiers["Bevel"].segments = 6
m = pv.clay_material("tile", 0)
nodes = m.node_tree.nodes
vc = [n for n in nodes if n.type == "VERTEX_COLOR"][0]
rgbn = nodes.new("ShaderNodeRGB")
rgbn.outputs[0].default_value = (0.035, 0.14, 0.15, 1)
bsdf = nodes.get("Principled BSDF")
m.node_tree.links.new(rgbn.outputs[0], bsdf.inputs["Base Color"])
tile.data.materials.append(m)
for p in tile.data.polygons:
    p.use_smooth = True


def light(name, loc, energy, size, col=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = col
    ob = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (head - mathutils.Vector(loc)).to_track_quat("-Z", "Y").to_euler()


s = height
light("key", (head.x + s * 0.8, head.y + s * 1.2, head.z + s * 0.9), 70 * s * s, s * 0.7, (1, 0.93, 0.85))
light("fill", (head.x - s * 1.0, head.y + s * 0.9, head.z + s * 0.1), 22 * s * s, s, (0.8, 0.88, 1))
light("rim", (head.x - s * 0.3, head.y - s * 1.0, head.z + s * 0.9), 60 * s * s, s * 0.6)
cd = bpy.data.cameras.new("cam")
cd.lens = 85
cam = bpy.data.objects.new("cam", cd)
bpy.context.collection.objects.link(cam)
d = height * 2.05
az = math.radians(18)
cam.location = (head.x + d * math.sin(az), head.y + d * math.cos(az), head.z + d * 0.06)
cam.rotation_euler = (head - cam.location).to_track_quat("-Z", "Y").to_euler()
sc.camera = cam
# centre the tile behind the head along the view line, facing the camera
view = (head - cam.location).normalized()
tile.location = head + view * (height * 0.35) + mathutils.Vector((0, 0, -height * 0.03))
tile.rotation_euler = (-view).to_track_quat("Z", "Y").to_euler()
sc.render.filepath = out
bpy.ops.render.render(write_still=True)
