"""
Title cards for the trailer (transparent 1920x1080 PNGs laid over darkened footage by edit.py): the clay logo and
chunky Lilita One lines with a soft clay-brown shadow.

  Tools/.venv/bin/python Tools/trailer/cards.py
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUT = os.path.join(ROOT, "Tools/trailer/cards")
FONT = os.path.join(ROOT, "Game/Assets/Saltmoss/Art/Fonts/LilitaOne-Regular.ttf")
BODY = os.path.join(ROOT, "Game/Assets/Saltmoss/Art/Fonts/Mali-Bold.ttf")
LOGO = os.path.join(ROOT, "Docs/media/logo.png")
W, H = 1920, 1080
CREAM = (246, 238, 219, 255)


def text_layer(lines, y0, size, font=FONT, spacing=1.15, color=CREAM):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = ImageFont.truetype(font, size)
    y = y0
    for line in lines:
        w = d.textlength(line, font=f)
        d.text(((W - w) / 2, y), line, font=f, fill=color)
        y += int(size * spacing)
    a = layer.split()[3]
    sh = Image.new("RGBA", (W, H), (40, 28, 22, 0))
    sa = Image.new("L", (W, H), 0)
    sa.paste(a, (5, 8))
    sh.putalpha(sa.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.8)))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(sh)
    out.alpha_composite(layer)
    return out


def logo_layer(width, y):
    lg = Image.open(LOGO).convert("RGBA")
    s = width / lg.width
    lg = lg.resize((int(lg.width * s), int(lg.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(lg, ((W - lg.width) // 2, y))
    return out


def save(name, *layers):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for l in layers:
        img.alpha_composite(l)
    img.save(os.path.join(OUT, name + ".png"))
    print("[card]", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    save("c_title", logo_layer(1250, 250), text_layer(["a cosy claymation fishing tale"], 760, 54, BODY))
    save("c_sea", text_layer(["Haul pots. Cast lines.", "Dredge the deep."], 380, 120))
    save("c_home", text_layer(["Bring the harbour", "back to life."], 380, 120))
    save("c_end", logo_layer(1150, 200), text_layer(["Free for macOS · Windows · Linux"], 700, 62), text_layer(["github.com/gazhenko/saltmoss-harbor"], 800, 40, BODY))


if __name__ == "__main__":
    main()
