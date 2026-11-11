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

CX, CY, R = 540, 900, 470     # ballon rond (comme la capture de référence)
NECK = 150                    # demi-largeur du goulot / tube
NECK_Y = CY - int(math.sqrt(R * R - NECK * NECK))   # où le goulot rejoint le ballon
TUBE_Y = 110                  # hauteur de la patate tenue dans le tube
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
        self.shape.elasticity = 0.62
        self.shape.friction = 0.5
        space.add(self.body, self.shape)
        self.lvl, self.born, self.pop = lvl, t, pop


def make_space():
    sp = pymunk.Space()
    sp.gravity = (0, 2200)
    sp.damping = 0.96
    sp.iterations = 20
    a0 = math.asin(NECK / R)                      # demi-ouverture du ballon en haut
    n = 140
    pts = []
    for k in range(n + 1):                        # arc complet sauf l'ouverture du haut
        ang = -math.pi / 2 + a0 + (2 * math.pi - 2 * a0) * k / n
        pts.append((CX + R * math.cos(ang), CY + R * math.sin(ang)))
    segs = list(zip(pts[:-1], pts[1:]))
    segs += [((CX - NECK, -400), (CX - NECK, NECK_Y)), ((CX + NECK, -400), (CX + NECK, NECK_Y))]
    for a, b in segs:
        s_ = pymunk.Segment(sp.static_body, a, b, 8)
        s_.elasticity, s_.friction = 0.9, 0.5
        sp.add(s_)
    return sp


def simulate(seed, max_t=60.0):
    """Renvoie (frames d'état, événements) ou None si échec. Une frame = liste (lvl, x, y, angle, scale)."""
    rnd = random.Random(seed)
    sp = make_space()
    pots, events, frames, rings = [], [], [], []
    held = None            # (lvl, x, tdrop)
    t, next_drop, score, boss_t = 0.0, 0.9, 0, None
    tube_x, tube_target = CX, CX
    announced_intro = False
    nframes = int(max_t * FPS)
    for f in range(nframes):
        t = f / FPS
        # --- flux continu : seules des patates niveau 1 tombent du haut de l'écran, trajectoire non droite
        if boss_t is None and t >= next_drop:
            lvl = 0
            x = rnd.uniform(CX - NECK + RADII[0] + 8, CX + NECK - RADII[0] - 8)
            pots.append(Potato(sp, lvl, x, -90, vx=rnd.uniform(-420, 420), vy=rnd.uniform(250, 600), t=t))
            pots[-1].body.angular_velocity = rnd.uniform(-6, 6)
            events.append({"t": round(t, 3), "kind": "drop", "level": lvl})
            next_drop = t + rnd.uniform(0.33, 0.52)
        tube_x = CX
        # --- physique
        for _ in range(SUB):
            # petit aimant entre patates identiques (niveau >=2) pour que la chaîne aboutisse
            for i, a in enumerate(pots):
                if a.lvl > 5:
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
        if any(p.body.position.y < NECK_Y + 30 and t > 2 and p.body.velocity.length < 60 and p.body.position.y > 0 and t - p.born > 3
               for p in pots):
            return None
        frames.append({"t": t, "tube_x": tube_x, "held": None, "score": score,
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
    return Image.new("RGBA", (W, H), (5, 5, 14, 255))          # noir comme la capture


def build_vase():
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((CX - R, CY - R, CX + R, CY + R), fill=(3, 3, 10, 255))
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(ring)
    a0 = math.asin(NECK / R)
    n = 720
    for k in range(n + 1):
        u = k / n
        ang = -math.pi / 2 + a0 + (2 * math.pi - 2 * a0) * u
        x, y = CX + R * math.cos(ang), CY + R * math.sin(ang)
        c = hsv(0.5 - u * 1.0)                      # cyan en haut à gauche -> jaune en bas -> violet à droite
        g.ellipse((x - 7, y - 7, x + 7, y + 7), fill=c + (255,))
    soft = ring.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(layer, soft)
    layer = Image.alpha_composite(layer, ring)
    # tube : deux traits blancs lumineux jusqu'en haut
    tube = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    td = ImageDraw.Draw(tube)
    for x in (CX - NECK, CX + NECK):
        td.rectangle((x - 4, 0, x + 4, NECK_Y), fill=(255, 255, 255, 255))
    tsoft = tube.filter(ImageFilter.GaussianBlur(10))
    layer = Image.alpha_composite(layer, tsoft)
    layer = Image.alpha_composite(layer, tube)
    return layer


def draw_tube(img, tx, held_sprite):
    if held_sprite is not None:
        img.alpha_composite(held_sprite, (int(tx - held_sprite.width / 2), int(TUBE_Y - held_sprite.height / 2)))


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
    icon_h = 88
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
    bann = [{"t": 0.7, "level": 0}] + [{"t": e["t"], "level": e["level"]} for e in merges]   # le nom s'écrit à CHAQUE fusion
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
        text_c(img, (W // 2, 1500), f"SCORE: {fr['score']}", 84, sw=0)
        gap = 20
        bd = 104
        tw = 7 * bd + 6 * gap
        od2 = ImageDraw.Draw(img)
        for l in range(7):
            ix = (W - tw) // 2 + l * (bd + gap)
            od2.ellipse((ix, 1590, ix + bd, 1590 + bd), fill=(26, 28, 48, 255), outline=(90, 94, 120, 255), width=4)
            if t >= discovered_at.get(l, 1e9):
                ic = icons[l]
                img.alpha_composite(ic, (ix + (bd - ic.width) // 2, 1590 + (bd - ic.height) // 2))
            else:
                od2.text((ix + bd // 2, 1590 + bd // 2), "?", font=font(60), fill=(200, 205, 230), anchor="mm")
        # boss : flash + vignette
        if t >= boss_t:
            ab = t - boss_t
            if ab < 0.5:
                fl = Image.new("RGBA", (W, H), (255, 255, 255, int(220 * (1 - ab / 0.5))))
                img.alpha_composite(fl)
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
            if 22 <= boss_t <= 45 or seed is not None:
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
