"""
Build .claymesh models from Tools/clay/models/*.py (each module defines OUT = "group/id" and build() -> Model,
or MODELS = {"group/id": fn}). Optionally render Blender previews and a contact sheet.

  Tools/.venv/bin/python Tools/clay/build.py pip walter          # specific modules
  Tools/.venv/bin/python Tools/clay/build.py --all               # everything
  Tools/.venv/bin/python Tools/clay/build.py pip --preview [--views threequarter,front] [--show mouth_smile]
"""
import argparse
import importlib
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))
MODELS_OUT = os.path.join(ROOT, "Game/Assets/Saltmoss/Models")
PREVIEWS = os.path.join(HERE, "previews")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "models"))


def targets(mod):
    if hasattr(mod, "MODELS"):
        return list(mod.MODELS.items())
    return [(mod.OUT, mod.build)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modules", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", default="", help="comma list of ids inside a multi-model module")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--views", default="threequarter,front,side,back")
    ap.add_argument("--res", default="560")
    ap.add_argument("--show", default="")
    ap.add_argument("--hide", default="")
    ap.add_argument("--row", action="store_true", help="preview all built models side by side in one image")
    ap.add_argument("--tag", default="row")
    a = ap.parse_args()
    mods = a.modules
    if a.all:
        mods = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "models")) if f.endswith(".py") and not f.startswith("_"))
    only = set(filter(None, a.only.split(",")))
    built = []
    for name in mods:
        mod = importlib.import_module(name)
        for out, fn in targets(mod):
            if only and out.split("/")[-1] not in only:
                continue
            t = time.time()
            m = fn()
            path = os.path.join(MODELS_OUT, out + ".claymesh")
            m.save(path)
            print(f"   ({time.time() - t:.1f}s)")
            built.append(path)
    if a.preview and built:
        os.makedirs(PREVIEWS, exist_ok=True)
        cmd = ["blender", "-b", "--factory-startup", "--python", os.path.join(HERE, "preview_blender.py"), "--", PREVIEWS, *built,
               "--views", a.views, "--res", a.res]
        if a.show:
            cmd += ["--show", a.show]
        if a.hide:
            cmd += ["--hide", a.hide]
        if a.row:
            cmd += ["--row", "--tag", a.tag]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:])
        else:
            for line in r.stdout.splitlines():
                if "Error" in line or "Traceback" in line:
                    print(line)
        sheet(built, a.views.split(","), a.row, a.tag)


def sheet(paths, views, row, tag):
    from PIL import Image
    names = [tag] if row else [os.path.splitext(os.path.basename(p))[0] for p in paths]
    for n in names:
        ims = [os.path.join(PREVIEWS, f"{n}_{v}.png") for v in views]
        ims = [Image.open(p) for p in ims if os.path.exists(p)]
        if not ims:
            continue
        w = sum(i.width for i in ims)
        h = max(i.height for i in ims)
        s = Image.new("RGB", (w, h))
        x = 0
        for i in ims:
            s.paste(i, (x, 0))
            x += i.width
        out = os.path.join(PREVIEWS, f"{n}_sheet.jpg")
        s.save(out, quality=88)
        print("[preview]", out)


if __name__ == "__main__":
    main()
