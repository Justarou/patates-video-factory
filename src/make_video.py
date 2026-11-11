"""Simulation 'Suika' de patates (pymunk) + rendu 2D 1080x1920 -> video muette + events.json.

usage: python src/make_video.py OUT_DIR [--seed N] [--preview]
"""
import sys, os, json, math, random, subprocess
import numpy as np
import pymunk
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
W, H, FPS = 1080, 1920, 30
SUB = 4                      # sous-pas physique par frame
DT = 1.0 / FPS / SUB

NAMES = ["LA PATATE CHIPS", "LA PATATE NUGGETS", "LA PATATE RACLETTE", "LA PATATE KEBAB",
         "LA PATATE SAUCE BLANCHE", "LA PATATE BUFFET À VOLONTÉ", "LA PATATE FONDUE SAVOYARDE INFINIE"]
SHORT = ["Chips", "Nuggets", "Raclette", "Kebab", "Sauce blanche", "Buffet", "Boss"]
SPRITE_FILES = ["01_patate_chips", "02_patate_nuggets", "03_patate_raclette", "04_patate_kebab",
                "05_patate_sauce_blanche", "06_patate_buffet_a_volonte",
                "07_BOSS_patate_fondue_savoyarde_infinie"]
RADII = [56, 72, 90, 112, 138, 168, 198]          # rayon de collision (px)

VX0, VX1 = 140, 940           # vase : bords intérieurs
VTOP, VBOT = 800, 1540        # haut visible / sol du vase
TUBE_Y = 700                  # bas du tube (la patate y est tenue)
FONT_B = next(p for p in [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"] if os.path.exists(p))


def font(sz):
    return ImageFont.truetype(FONT_B, sz)


# ---------------------------------------------------------------- sprites
def load_sprites():
    out = []
    for lvl, name in enumerate(SPRITE_FILES):
        im = Image.open(os.path.join(ROOT, "assets", "sprites", name + ".png")).convert("RGBA")
        bb = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
        body = 0.5 * min(bb[2] - bb[0], bb[3] - bb[1]) * 0.96   # rayon visuel du corps (sur 512)
        size = int(round(RADII[lvl] / body * 512))
        out.append(im.resize((size, size), Image.LANCZOS))
    return out


# ---------------------------------------------------------------- simulation
class Potato:
    __slots__ = ("lvl", "body", "shape", "born", "pop")

    def __init__(self, space, lvl, x, y, vx=0.0, vy=0.0, t=0.0, pop=False):
        r = RADII[lvl]
        mass = (r / 56.0) ** 2
        self.body = pymunk.Body(mass, pymunk.moment_for_circle(mass, 0, r))
        self.body.position = (x, y)
        self.body.velocity = (vx, vy)
        self.shape = pymunk.Circle(self.body, r)
        self.shape.elasticity = 0.12
        self.shape.friction = 0.7
        space.add(self.body, self.shape)
        self.lvl, self.born, self.pop = lvl, t, pop


def make_space():
    sp = pymunk.Space()
    sp.gravity = (0, 2200)
    sp.damping = 0.88
    sp.iterations = 20
    for a, b in [((VX0 - 12, 300), (VX0 - 12, VBOT + 12)), ((VX1 + 12, 300), (VX1 + 12, VBOT + 12)),
                 ((VX0 - 12, VBOT + 12), (VX1 + 12, VBOT + 12))]:
        s = pymunk.Segment(sp.static_body, a, b, 12)
        s.elasticity, s.friction = 0.1, 0.8
        sp.add(s)
    return sp


def simulate(seed, max_t=60.0):
    """Renvoie (frames d'état, événements) ou None si échec. Une frame = liste (lvl, x, y, angle, scale)."""
    rnd = random.Random(seed)
    sp = make_space()
    pots, events, frames, rings = [], [], [], []
    held = None            # (lvl, x, tdrop)
    t, next_drop, score, boss_t = 0.0, 0.9, 0, None
    tube_x, tube_target = (VX0 + VX1) / 2, (VX0 + VX1) / 2
    announced_intro = False
    nframes = int(max_t * FPS)
    for f in range(nframes):
        t = f / FPS
        # --- director : lâcher une patate
        if boss_t is None and held is None and t >= next_drop:
            present = {}
            for p in pots:
                if p.lvl <= 5:
                    present.setdefault(p.lvl, []).append(p)
            lvl = rnd.choice([0, 0, 0, 1, 1, 2])
            tgt = None
            for l in (lvl, 0, 1, 2):
                cands = [p for p in present.get(l, []) if p.body.position.y < VBOT - 20]
                if cands and rnd.random() < 0.85:
                    tgt = max(cands, key=lambda p: -p.body.position.y); lvl = l; break
            if tgt is not None:
                x = tgt.body.position.x + rnd.uniform(-10, 10)
            else:
                x = rnd.uniform(VX0 + RADII[lvl] + 8, VX1 - RADII[lvl] - 8)
            x = min(max(x, VX0 + RADII[lvl] + 6), VX1 - RADII[lvl] - 6)
            tube_target = x
            held = (lvl, x, t + 0.35)
        tube_x += (tube_target - tube_x) * 0.35
        if held and t >= held[2]:
            lvl, x, _ = held
            pots.append(Potato(sp, lvl, x, TUBE_Y + 10, vy=300, t=t))
            events.append({"t": round(t, 3), "kind": "drop", "level": lvl})
            held = None
            next_drop = t + rnd.uniform(0.55, 0.85)
        # --- physique
        for _ in range(SUB):
            # petit aimant entre patates identiques (niveau >=2) pour que la chaîne aboutisse
            for i, a in enumerate(pots):
                if a.lvl < 2 or a.lvl > 5:
                    continue
                for b in pots[i + 1:]:
                    if b.lvl == a.lvl:
                        d = b.body.position - a.body.position
                        dist = abs(d)
                        if dist > 1:
                            fmag = 9000 * a.body.mass * min(1.0, 320 / dist)
                            a.body.apply_force_at_world_point(d / dist * fmag, a.body.position)
                            b.body.apply_force_at_world_point(-d / dist * fmag, b.body.position)
            sp.step(DT)
        # --- fusions
        merged = True
        while merged:
            merged = False
            for i, a in enumerate(pots):
                for b in pots[i + 1:]:
                    if a.lvl == b.lvl and a.lvl < 6:
                        d = abs(a.body.position - b.body.position)
                        if d <= RADII[a.lvl] + RADII[b.lvl] + 3:
                            m = (a.body.position + b.body.position) * 0.5
                            v = (a.body.velocity + b.body.velocity) * 0.5
                            nl = a.lvl + 1
                            for q in (a, b):
                                sp.remove(q.body, q.shape)
                            pots.remove(a); pots.remove(b)
                            pots.append(Potato(sp, nl, m.x, m.y, v.x * 0.5, v.y * 0.5, t, pop=True))
                            score += 10 * 2 ** nl
                            events.append({"t": round(t, 3), "kind": "merge", "level": nl,
                                           "x": round(m.x), "y": round(m.y)})
                            if nl == 6:
                                boss_t = t
                            merged = True
                            break
                if merged:
                    break
        # --- overflow = échec
        if any(p.body.position.y - RADII[p.lvl] < VTOP - 260 and t > 2 and p.body.velocity.length < 60
               for p in pots):
            return None
        frames.append({"t": t, "tube_x": tube_x, "held": held, "score": score,
                       "pots": [(p.lvl, p.body.position.x, p.body.position.y, p.body.angle, p.born, p.pop)
                                for p in pots]})
        if boss_t is not None and t > boss_t + 4.5:
            break
    if boss_t is None:
        return None
    return frames, events, boss_t


# ---------------------------------------------------------------- décor statique
def hsv(h, s=1.0, v=1.0):
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def build_background():
    yy = np.linspace(0, 1, H)[:, None]
    top, bot = np.array([14, 10, 46]), np.array([34, 14, 70])
    bg = (top * (1 - yy) + bot * yy)[:, None, :].repeat(W, axis=1)
    img = Image.fromarray(bg.astype("uint8"), "RGB")
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    for _ in range(140):
        x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.choice([1, 1, 2, 2, 3])
        c = rnd.randrange(120, 255)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(c, c, 255))
    return img.convert("RGBA")


def build_vase():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    inner = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(inner).rectangle((VX0, VTOP, VX1, VBOT), fill=(8, 6, 28, 190))
    layer = Image.alpha_composite(layer, inner)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    pts = [(VX0 - 8, VTOP - 20), (VX0 - 8, VBOT + 8), (VX1 + 8, VBOT + 8), (VX1 + 8, VTOP - 20)]
    n = 240
    path = []
    for a, b in zip(pts[:-1], pts[1:]):
        for k in range(n):
            u = k / n
            path.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
    for i, (x, y) in enumerate(path):
        c = hsv(i / len(path) * 1.5)
        g.ellipse((x - 11, y - 11, x + 11, y + 11), fill=c + (255,))
    soft = glow.filter(ImageFilter.GaussianBlur(26))
    layer = Image.alpha_composite(layer, soft)
    layer = Image.alpha_composite(layer, soft)
    layer = Image.alpha_composite(layer, glow)
    return layer


def draw_tube(img, tx, held_sprite):
    d = ImageDraw.Draw(img)
    x0, x1 = tx - 78, tx + 78
    d.rounded_rectangle((x0, 440, x1, TUBE_Y - 40), 18, fill=(105, 112, 140), outline=(210, 220, 255), width=5)
    d.rectangle((x0 + 16, 440, x0 + 34, TUBE_Y - 40), fill=(150, 160, 190))
    d.rounded_rectangle((x0 - 14, TUBE_Y - 52, x1 + 14, TUBE_Y - 14), 10, fill=(80, 86, 112),
                        outline=(210, 220, 255), width=5)
    if held_sprite is not None:
        img.alpha_composite(held_sprite, (int(tx - held_sprite.width / 2), int(TUBE_Y - 10 - held_sprite.height / 2 + 40)))


def text_c(img, xy, txt, size, fill=(255, 255, 255), stroke=(20, 8, 40), sw=8, alpha=255):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(size)
    d.text(xy, txt, font=f, fill=fill + (alpha,), anchor="mm", stroke_width=sw, stroke_fill=stroke + (alpha,))
    img.alpha_composite(layer)


def fit_font(txt, maxw, size):
    while size > 20 and ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(txt, font=font(size)) > maxw:
        size -= 4
    return size


# ---------------------------------------------------------------- rendu
def render(frames, events, boss_t, sprites, out_dir, preview=False):
    bg, vase = build_background(), build_vase()
    sil = []
    for im in sprites:                     # silhouettes pour les niveaux "?"
        a = im.getchannel("A")
        s = Image.new("RGBA", im.size, (40, 34, 80, 255)); s.putalpha(a)
        sil.append(s)
    icon_h = 92
    icons = [im.resize((icon_h, icon_h), Image.LANCZOS) for im in sprites]
    sil_i = [im.resize((icon_h, icon_h), Image.LANCZOS) for im in sil]
    merges = [e for e in events if e["kind"] == "merge"]
    discovered_at = {}
    for e in merges:
        discovered_at.setdefault(e["level"], e["t"])
    discovered_at[0] = 0.0

    # annonces vocales : intro chips + chaque fusion (une plus haute passe toujours)
    ann, last_end, last_lvl = [{"t": 0.7, "level": 0}], 0.7 + 1.2, 0
    for e in merges:
        if e["t"] >= last_end or e["level"] > last_lvl:
            ann.append({"t": e["t"], "level": e["level"]})
            last_end = e["t"] + [1.2, 1.2, 1.4, 1.4, 1.8, 2.0, 2.9][e["level"]]
            last_lvl = e["level"]
    for a in ann:
        a["t"] = round(a["t"], 3)
    total_t = frames[-1]["t"] + 0.2
    json.dump({"announcements": ann, "events": events, "duration": total_t, "boss_t": boss_t},
              open(os.path.join(out_dir, "events.json"), "w"), indent=1)

    out = os.path.join(out_dir, "video_silent.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out],
                          stdin=subprocess.PIPE)
    rings = []
    seen_merge = 0
    last_snap = None
    stride = 15 if preview else 1
    for fi, fr in enumerate(frames):
        t = fr["t"]
        if preview and fi % stride:
            continue
        img = bg.copy()
        img.alpha_composite(vase)
        # fusions -> anneaux
        while seen_merge < len(merges) and merges[seen_merge]["t"] <= t:
            rings.append(merges[seen_merge]); seen_merge += 1
        # patates
        for (lvl, x, y, ang, born, pop) in sorted(fr["pots"], key=lambda p: p[0]):
            sc = 1.0
            age = t - born
            if pop and age < 0.35:
                sc = 1.0 + 0.30 * math.sin(min(age / 0.35, 1) * math.pi) * (1 - age / 0.35 * 0.4)
            sp = sprites[lvl]
            if sc != 1.0:
                s2 = int(sp.width * sc); sp_ = sp.resize((s2, s2), Image.BICUBIC)
            else:
                sp_ = sp
            rot = sp_.rotate(-math.degrees(ang), resample=Image.BICUBIC, expand=True)
            img.alpha_composite(rot, (int(x - rot.width / 2), int(y - rot.height / 2)))
        # tube + patate tenue
        held_sp = None
        if fr["held"]:
            held_sp = sprites[fr["held"][0]]
        draw_tube(img, fr["tube_x"], held_sp)
        # anneaux de fusion
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        for r in list(rings):
            a = (t - r["t"]) / 0.5
            if a > 1:
                rings.remove(r); continue
            rad = RADII[r["level"]] * (1.0 + 1.3 * a)
            col = hsv(r["level"] / 7 + a * 0.3)
            od.ellipse((r["x"] - rad, r["y"] - rad, r["x"] + rad, r["y"] + rad),
                       outline=col + (int(255 * (1 - a)),), width=int(14 * (1 - a)) + 2)
        img.alpha_composite(ov)
        # HUD
        text_c(img, (W // 2, 170), "FUSIONNE LES PATATES", 64, fill=(255, 238, 120))
        text_c(img, (W // 2, 262), f"SCORE : {fr['score']}", 62)
        gap = 18
        tw = 7 * icon_h + 6 * gap
        for l in range(7):
            ix = (W - tw) // 2 + l * (icon_h + gap)
            if t >= discovered_at.get(l, 1e9):
                img.alpha_composite(icons[l], (ix, 330))
            else:
                img.alpha_composite(sil_i[l], (ix, 330))
                ImageDraw.Draw(img).text((ix + icon_h // 2, 330 + icon_h // 2), "?", font=font(54),
                                         fill=(255, 255, 255), anchor="mm")
        # bannière du nom annoncé
        cur = None
        for a in ann:
            dur = [1.2, 1.2, 1.4, 1.4, 1.8, 2.0, 3.6][a["level"]]
            if a["t"] <= t < a["t"] + dur:
                cur = a
        if cur:
            lvl, age = cur["level"], t - cur["t"]
            pop = 1.0 + 0.35 * max(0.0, 1 - age / 0.25)
            base = [76, 82, 88, 96, 104, 112, 118][lvl]
            txt = NAMES[lvl]
            lines = txt.split(" ", 2)
            lines = [" ".join(lines[:2]), lines[2]] if len(lines) == 3 else [txt]
            sz = min(fit_font(l, 980, int(base * pop * 1.2)) for l in lines)
            y0 = 1110 - (len(lines) - 1) * sz * 0.55
            for k, l in enumerate(lines):
                col = hsv(0.12 - lvl * 0.012, 0.85 - lvl * 0.06, 1)
                text_c(img, (W // 2, int(y0 + k * sz * 1.1)), l, sz, fill=col, sw=10 + lvl)
        # boss : flash + vignette
        if t >= boss_t:
            ab = t - boss_t
            if ab < 0.5:
                fl = Image.new("RGBA", (W, H), (255, 255, 255, int(220 * (1 - ab / 0.5))))
                img.alpha_composite(fl)
            if ab > 1.0:
                text_c(img, (W // 2, 1690), "NIVEAU MAX", 96, fill=(255, 90, 60))
        # tremblement croissant
        lv = max([p[0] for p in fr["pots"]] + [0])
        amp = 0
        for e in merges:
            if 0 <= t - e["t"] < 0.35:
                amp = max(amp, (2 + e["level"] * 4.0) * (1 - (t - e["t"]) / 0.35))
        if boss_t <= t < boss_t + 2.5:
            amp = max(amp, 26 * (1 - (t - boss_t) / 2.5))
        if amp > 0:
            img = ImageChops.offset(img, int(random.uniform(-amp, amp)), int(random.uniform(-amp, amp)))
        rgb = img.convert("RGB")
        if preview:
            rgb.save(os.path.join(out_dir, f"preview_{fi:04d}.png"))
        ff.stdin.write(rgb.tobytes())
    ff.stdin.close(); ff.wait()
    return total_t


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "build"
    os.makedirs(out_dir, exist_ok=True)
    seed = None
    if "--seed" in sys.argv:
        seed = int(sys.argv[sys.argv.index("--seed") + 1])
    preview = "--preview" in sys.argv
    sprites = load_sprites()
    res = None
    seeds = [seed] if seed is not None else range(1, 200)
    for s in seeds:
        res = simulate(s)
        if res:
            frames, events, boss_t = res
            dur = frames[-1]["t"]
            print(f"seed {s}: OK, boss à {boss_t:.1f}s, durée {dur:.1f}s, {len(events)} événements", flush=True)
            if 22 <= boss_t <= 48 or seed is not None:
                break
            res = None
        else:
            print(f"seed {s}: échec", flush=True)
    if not res:
        sys.exit("aucune graine valide")
    random.seed(1)
    render(frames, events, boss_t, sprites, out_dir, preview)
    print("vidéo muette écrite")


if __name__ == "__main__":
    main()
