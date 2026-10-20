import math, random, subprocess, wave, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
OUT = sys.argv[1]
random.seed(7)
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(sz): return ImageFont.truetype(FB, sz)
F_BIG, F_MED, F_SM = font(104), font(64), font(46)

SCENES = [("intro", 3.0), ("marinade", 4.0), ("skewer", 3.5), ("grill", 4.5), ("final", 3.0)]
TOTAL = sum(d for _, d in SCENES)

SKIN = (247, 205, 175); HAIR = (92, 52, 30); DRESS = (226, 64, 72); APRON = (250, 246, 238)
MEAT_RAW = (196, 70, 70); MEAT_DONE = (128, 62, 34); ONION = (236, 220, 236)

def clamp(v, a=0.0, b=1.0): return max(a, min(b, v))
def ease(t): t = clamp(t); return 1 - (1 - t) ** 3
def lerp(a, b, t): return a + (b - a) * t
def lerpc(c1, c2, t): return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))

def gradient(stops):
    arr = np.zeros((H, W, 3), np.uint8)
    ys = np.linspace(0, 1, H)
    pos = [p for p, _ in stops]; cols = np.array([c for _, c in stops], float)
    for ch in range(3):
        arr[:, :, ch] = np.interp(ys, pos, cols[:, ch])[:, None]
    return Image.fromarray(arr)

def outdoor_bg():
    img = gradient([(0, (88, 60, 140)), (0.35, (240, 110, 110)), (0.6, (255, 190, 110)), (1, (255, 210, 140))])
    d = ImageDraw.Draw(img)
    d.ellipse((620, 820, 900, 1100), fill=(255, 236, 170))  # sun
    for x, h in [(-40, 380), (120, 300), (900, 420), (1010, 330)]:  # trees
        d.polygon([(x, 1300 - h), (x - 110, 1320), (x + 110, 1320)], fill=(52, 70, 60))
    d.rectangle((0, 1300, W, H), fill=(92, 150, 80))
    d.rectangle((0, 1300, W, 1330), fill=(110, 170, 92))
    return img

def kitchen_bg():
    img = Image.new("RGB", (W, H), (250, 232, 210))
    d = ImageDraw.Draw(img)
    for y in range(0, 1350, 90):
        for x in range(0 if (y // 90) % 2 else -45, W, 90):
            d.rectangle((x + 3, y + 3, x + 87, y + 87), fill=(242, 222, 198))
    d.rectangle((640, 220, 980, 620), fill=(170, 210, 235), outline=(255, 255, 255), width=18)  # window
    d.line((810, 220, 810, 620), fill=(255, 255, 255), width=12)
    return img

BG_OUT, BG_KIT = outdoor_bg(), kitchen_bg()

def arm(d, sx, sy, ang, length, s):
    ex = sx + math.cos(math.radians(ang)) * length * s
    ey = sy + math.sin(math.radians(ang)) * length * s
    d.line((sx, sy, ex, ey), fill=SKIN, width=int(28 * s))
    r = 18 * s
    d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=SKIN)
    return ex, ey

def girl(d, x, y, s, la, ra, t, blink_off=0.0):
    """Feet at (x, y). la/ra: arm angles in degrees (0 = right, 90 = down). Returns hand points."""
    P = lambda dx, dy: (x + dx * s, y + dy * s)
    # long hair behind
    d.polygon([P(-92, -640), P(92, -640), P(110, -420), P(-110, -420)], fill=HAIR)
    # legs + shoes
    for dx in (-35, 35):
        d.rectangle((*P(dx - 14, -190), *P(dx + 14, -30)), fill=SKIN)
        d.ellipse((*P(dx - 30, -40), *P(dx + 30, 0)), fill=(60, 40, 40))
    # dress
    d.polygon([P(-70, -520), P(70, -520), P(130, -170), P(-130, -170)], fill=DRESS)
    d.polygon([P(-55, -430), P(55, -430), P(85, -200), P(-85, -200)], fill=APRON)
    d.ellipse((*P(-22, -360), *P(22, -316)), fill=(255, 150, 90))  # apron pocket heart-ish
    # arms
    lh = arm(d, *P(-68, -500), la, 210, s)
    rh = arm(d, *P(68, -500), ra, 210, s)
    # neck + head
    d.rectangle((*P(-18, -560), *P(18, -510)), fill=SKIN)
    d.ellipse((*P(-80, -720), *P(80, -545)), fill=SKIN)
    # fringe + bun
    d.chord((*P(-88, -735), *P(88, -600)), 180, 360, fill=HAIR)
    d.ellipse((*P(-40, -790), *P(40, -715)), fill=HAIR)
    d.rectangle((*P(-30, -740), *P(30, -728)), fill=(255, 90, 110))  # hair band
    # face
    blink = (t + blink_off) % 2.6 < 0.12
    for dx in (-30, 30):
        if blink:
            d.line((*P(dx - 12, -630), *P(dx + 12, -630)), fill=(40, 30, 30), width=int(6 * s))
        else:
            d.ellipse((*P(dx - 11, -645), *P(dx + 11, -617)), fill=(40, 30, 30))
            d.ellipse((*P(dx - 3, -641), *P(dx + 4, -634)), fill=(255, 255, 255))
        d.ellipse((*P(dx * 1.6 - 16, -605), *P(dx * 1.6 + 16, -585)), fill=(250, 160, 160))
    d.arc((*P(-28, -620), *P(28, -580)), 20, 160, fill=(170, 50, 60), width=int(7 * s))
    return lh, rh

def meat(d, cx, cy, r, done=0.0, shade=0.0):
    c = lerpc(MEAT_RAW, MEAT_DONE, done)
    c = lerpc(c, (70, 35, 20), shade * 0.35)
    d.rounded_rectangle((cx - r, cy - r, cx + r, cy + r), radius=int(r * 0.45), fill=c)
    hl = lerpc(c, (255, 200, 170), 0.35)
    d.rounded_rectangle((cx - r * 0.6, cy - r * 0.7, cx + r * 0.1, cy - r * 0.35), radius=int(r * 0.2), fill=hl)
    if done > 0.5:  # grill marks
        for k in (-0.4, 0.2):
            d.line((cx + k * r - r * 0.2, cy - r * 0.6, cx + k * r + r * 0.3, cy + r * 0.6), fill=(60, 30, 15), width=max(3, int(r * 0.12)))

def onion(d, cx, cy, r):
    d.ellipse((cx - r * 0.45, cy - r, cx + r * 0.45, cy + r), fill=ONION, outline=(170, 90, 160), width=max(3, int(r * 0.12)))

def pepper(d, cx, cy, r, col):
    d.rounded_rectangle((cx - r * 0.5, cy - r, cx + r * 0.5, cy + r), radius=int(r * 0.3), fill=col)

def skewer(d, x0, y, x1, items, r, done=0.0, rot=0.0):
    d.line((x0, y, x1, y), fill=(190, 190, 200), width=max(6, int(r * 0.18)))
    d.ellipse((x0 - r * 0.35, y - r * 0.35, x0 + r * 0.35, y + r * 0.35), fill=(150, 150, 160))
    for i, (kind, px) in enumerate(items):
        sh = 0.5 + 0.5 * math.sin(rot + i)
        if kind == "m": meat(d, px, y, r, done, sh)
        elif kind == "o": onion(d, px, y, r)
        elif kind == "p": pepper(d, px, y, r, lerpc((230, 60, 40), (150, 50, 30), done * 0.6))
        elif kind == "g": pepper(d, px, y, r, lerpc((80, 170, 60), (70, 110, 40), done * 0.6))

def text_c(d, y, txt, f, fill=(255, 255, 255), stroke=(60, 20, 20), sw=7, x=None):
    w = d.textlength(txt, font=f)
    d.text(((W - w) / 2 if x is None else x, y), txt, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)

def pill(d, y, txt, f, bg=(255, 255, 255), fg=(200, 50, 40)):
    w = d.textlength(txt, font=f); h = f.size
    x = (W - w) / 2
    d.rounded_rectangle((x - 40, y - 22, x + w + 40, y + h + 30), radius=40, fill=bg)
    d.text((x, y), txt, font=f, fill=fg)

class Particles:
    def __init__(self): self.p = []
    def emit(self, x, y, kind, n=1):
        for _ in range(n):
            self.p.append(dict(x=x + random.uniform(-200, 200), y=y, vx=random.uniform(-40, 40),
                               vy=random.uniform(-260, -120) if kind == "smoke" else random.uniform(-600, -300),
                               life=0.0, maxl=random.uniform(1.6, 2.6) if kind == "smoke" else random.uniform(0.5, 1.1),
                               r=random.uniform(40, 80), kind=kind))
    def step(self, dt):
        for q in self.p:
            q["x"] += q["vx"] * dt + math.sin(q["life"] * 3) * 1.2; q["y"] += q["vy"] * dt; q["life"] += dt
        self.p = [q for q in self.p if q["life"] < q["maxl"]]
    def draw(self, layer):
        d = ImageDraw.Draw(layer)
        for q in self.p:
            k = q["life"] / q["maxl"]
            if q["kind"] == "smoke":
                r = q["r"] * (1 + k * 1.5); a = int(110 * (1 - k))
                d.ellipse((q["x"] - r, q["y"] - r, q["x"] + r, q["y"] + r), fill=(235, 235, 240, a))
            else:
                r = 7 * (1 - k) + 2
                d.ellipse((q["x"] - r, q["y"] - r, q["x"] + r, q["y"] + r), fill=(255, 200, 60, int(255 * (1 - k))))

parts = Particles()

# ---------------- scenes ----------------
def sc_intro(t, dur):
    img = BG_OUT.copy(); d = ImageDraw.Draw(img)
    wave_a = -60 + 25 * math.sin(t * 9)
    gy = lerp(2200, 1800, ease(t / 0.6))
    girl(d, 540, gy, 1.45, 120, wave_a, t)
    a = ease((t - 0.3) / 0.5)
    y0 = lerp(-200, 260, a)
    text_c(d, y0, "ИДЕАЛЬНЫЙ", F_BIG, fill=(255, 235, 120))
    text_c(d, y0 + 125, "ШАШЛЫК", font(150), fill=(255, 255, 255))
    if t > 0.9:
        pill(d, 610, "всего 3 шага", F_MED)
    return img

INGR = [("Свиная шея — 1 кг", "m"), ("Лук — 3 шт", "o"), ("Соль, перец, зира", "s"), ("Минералка 200 мл", "w")]
def sc_marinade(t, dur):
    img = BG_KIT.copy(); d = ImageDraw.Draw(img)
    stir = 25 * math.sin(t * 7)
    lh, rh = girl(d, 330, 1820, 1.55, 100, 25 + stir, t, 0.7)
    # spoon in right hand
    d.line((rh[0], rh[1], rh[0] + 90, rh[1] + 150), fill=(140, 90, 50), width=16)
    # table
    d.rectangle((0, 1380, W, H), fill=(170, 110, 70)); d.rectangle((0, 1380, W, 1410), fill=(195, 135, 90))
    # bowl
    bx, by = 720, 1390
    d.ellipse((bx - 260, by - 110, bx + 260, by + 40), fill=(80, 140, 200))
    d.ellipse((bx - 235, by - 100, bx + 235, by + 10), fill=(150, 70, 60))
    d.chord((bx - 260, by - 260, bx + 260, by + 120), 0, 180, fill=(70, 125, 190))
    # contents inside (accumulate)
    random.seed(3)
    for i, (_, kind) in enumerate(INGR):
        tt = t - 0.4 - i * 0.65
        if tt <= 0: continue
        for j in range(5):
            ox = random.uniform(-170, 170); oy = random.uniform(-125, -80)
            fall = ease(tt / 0.45)
            cy = lerp(-100 - j * 60, by + oy, fall); cx = bx + ox + (math.sin(t * 7 + j) * 6 if fall >= 1 else 0)
            if kind == "m": meat(d, cx, cy, 40)
            elif kind == "o": onion(d, cx, cy, 34)
            elif kind == "s": d.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=(120, 60, 20))
            else: d.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=(200, 230, 255))
    d.chord((bx - 260, by - 260, bx + 260, by + 120), 0, 180, fill=(70, 125, 190))
    # captions
    pill(d, 120, "ШАГ 1 · МАРИНАД", F_MED, bg=(220, 60, 60), fg=(255, 255, 255))
    for i, (name, _) in enumerate(INGR):
        a = ease((t - 0.4 - i * 0.65) / 0.3)
        if a <= 0: continue
        x = lerp(W, 470, a)
        d.rounded_rectangle((x - 20, 300 + i * 95, x + 590, 375 + i * 95), radius=30, fill=(255, 255, 255))
        d.text((x + 5, 310 + i * 95), "✓ " + name, font=F_SM, fill=(60, 40, 40))
    if t > 3.0:
        pill(d, 1700, "оставить на 4–6 часов", F_SM, fg=(120, 60, 40))
    return img

ORDER = ["m", "o", "m", "p", "m", "g", "m", "o", "m"]
def sc_skewer(t, dur):
    img = BG_KIT.copy(); d = ImageDraw.Draw(img)
    _, rh = girl(d, 220, 1820, 1.55, 105, -5, t, 1.3)
    d.rectangle((0, 1380, W, H), fill=(170, 110, 70)); d.rectangle((0, 1380, W, 1410), fill=(195, 135, 90))
    x0, y, x1 = rh[0] + 20, rh[1], W + 40
    items = []
    for i, k in enumerate(ORDER):
        tt = (t - 0.2 - i * 0.28) / 0.3
        if tt <= 0: continue
        target = x1 - 100 - i * 72
        items.append((k, lerp(W + 120, target, ease(tt))))
    skewer(d, x0, y, x1, items, 46)
    # a second finished skewer on the table
    if t > 2.3:
        a = ease((t - 2.3) / 0.4)
        y2 = lerp(H + 100, 1560, a)
        skewer(d, 120, y2, W - 40, [(k, W - 140 - i * 92) for i, k in enumerate(ORDER)], 52)
    pill(d, 120, "ШАГ 2 · НАНИЗЫВАЕМ", F_MED, bg=(220, 60, 60), fg=(255, 255, 255))
    text_c(d, 290, "мясо + лук + перчик", F_SM, fill=(255, 255, 255), stroke=(120, 60, 40), sw=6)
    return img

def sc_grill(t, dur, dt):
    img = BG_OUT.copy().convert("RGBA"); d = ImageDraw.Draw(img)
    fan = -100 + 35 * math.sin(t * 14)
    lh, rh = girl(d, 880, 1800, 1.4, fan + 0, 140, t, 0.3)
    # fan (cardboard) in left hand
    fx, fy = lh
    d.polygon([(fx, fy), (fx - 90, fy - 150), (fx + 40, fy - 170)], fill=(200, 160, 100))
    # mangal
    mx0, mx1, my = 60, 700, 1330
    for lx in (110, 650):
        d.rectangle((lx - 12, my + 120, lx + 12, my + 420), fill=(50, 50, 55))
    d.rectangle((mx0, my, mx1, my + 140), fill=(60, 60, 66))
    d.rectangle((mx0, my, mx1, my + 18), fill=(90, 90, 98))
    random.seed(11)
    for i in range(30):  # coals
        cx = random.uniform(mx0 + 30, mx1 - 30); cy = my + random.uniform(-10, 20)
        g = 0.5 + 0.5 * math.sin(t * random.uniform(4, 9) + i)
        c = lerpc((150, 30, 10), (255, 170, 40), g)
        d.ellipse((cx - 26, cy - 18, cx + 26, cy + 18), fill=c)
    done = ease(t / (dur * 0.85))
    for k in range(4):
        yy = my - 30 - k * 70
        skewer(d, mx0 - 30, yy, mx1 + 30,
               [(ORDER[i], mx1 - 40 - i * 70) for i in range(9)], 32, done, t * 4 + k)
    if True:
        parts.emit((mx0 + mx1) / 2, my - 60, "smoke", 1)
    parts.emit((mx0 + mx1) / 2, my, "spark", 2)
    parts.step(dt)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); parts.draw(layer)
    img = Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(3))).convert("RGB")
    d = ImageDraw.Draw(img)
    pill(d, 120, "ШАГ 3 · НА УГЛЯХ", F_MED, bg=(220, 60, 60), fg=(255, 255, 255))
    mins = int(lerp(0, 20, clamp(t / (dur * 0.9))))
    text_c(d, 290, f"{mins:02d}:00 мин", font(90), fill=(255, 235, 120))
    text_c(d, 410, "переворачивай каждые 3–4 мин", F_SM, sw=6)
    return img

def sc_final(t, dur):
    img = BG_OUT.copy(); d = ImageDraw.Draw(img)
    girl(d, 790, 1760, 1.35, 150, -75 + 8 * math.sin(t * 10), t, 0.9)
    d.rectangle((0, 1450, W, H), fill=(170, 110, 70)); d.rectangle((0, 1450, W, 1480), fill=(195, 135, 90))
    # plate with shashlik
    a = ease(t / 0.5)
    py = lerp(H + 200, 1500, a)
    d.ellipse((60, py - 120, 980, py + 120), fill=(240, 240, 245))
    d.ellipse((120, py - 85, 920, py + 85), fill=(255, 255, 255))
    for k, off in enumerate((-35, 30)):
        skewer(d, 140, py + off, 900, [(ORDER[i], 840 - i * 78) for i in range(9)], 40, 1.0, k)
    for hx in (220, 470, 700):  # herbs
        d.ellipse((hx - 30, py + 50, hx + 30, py + 80), fill=(70, 160, 60))
    s = 1 + 0.06 * math.sin(t * 8)
    text_c(d, 260, "ПРИЯТНОГО", font(int(110 * s)), fill=(255, 235, 120))
    text_c(d, 390, "АППЕТИТА!", font(int(110 * s)), fill=(255, 255, 255))
    if t > 0.8:
        pill(d, 590, "Сохрани рецепт ↓", F_MED)
    return img

# ---------------- render ----------------
proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", OUT + ".wav",
                         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT],
                        stdin=subprocess.PIPE) if len(sys.argv) < 3 else None

def make_audio(path):
    sr = 44100; n = int(sr * TOTAL); tt = np.arange(n) / sr
    out = np.zeros(n)
    bpm = 116; beat = 60 / bpm
    chords = [57, 53, 48, 55]  # A F C G (midi roots)
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    nb = int(TOTAL / beat) + 1
    rng = np.random.default_rng(1)
    for b in range(nb):
        st = int(b * beat * sr); L = int(beat * sr)
        if st >= n: break
        seg = slice(st, min(n, st + L)); ts = tt[seg] - b * beat
        # kick
        out[seg] += 0.55 * np.sin(2 * np.pi * (50 + 90 * np.exp(-ts * 30)) * ts) * np.exp(-ts * 9)
        # bass + pluck chord
        root = chords[(b // 4) % 4]
        out[seg] += 0.22 * np.sign(np.sin(2 * np.pi * hz(root - 12) * ts)) * np.exp(-ts * 5)
        for iv in (0, 4 if root in (53, 48, 55) else 3, 7):
            f = hz(root + 12 + iv)
            out[seg] += 0.07 * np.sin(2 * np.pi * f * ts) * np.exp(-ts * 4)
        # offbeat hat
        hs = st + L // 2
        if hs < n:
            hl = min(n - hs, int(0.05 * sr))
            out[hs:hs + hl] += 0.12 * rng.standard_normal(hl) * np.exp(-np.arange(hl) / sr * 80)
    # sizzle during grill scene
    g0 = sum(d for _, d in SCENES[:3]); g1 = g0 + SCENES[3][1]
    i0, i1 = int(g0 * sr), int(g1 * sr)
    noise = rng.standard_normal(i1 - i0)
    noise = noise - np.convolve(noise, np.ones(8) / 8, "same")  # high-pass-ish
    crackle = (rng.random(i1 - i0) < 0.002) * rng.uniform(0.3, 1, i1 - i0)
    env = np.minimum(1, np.minimum(np.arange(i1 - i0), np.arange(i1 - i0)[::-1]) / (0.3 * sr))
    out[i0:i1] += (0.18 * noise + crackle) * env
    fade = np.minimum(1, (n - np.arange(n)) / (0.8 * sr))
    out = out * fade / max(1e-9, np.abs(out).max()) * 0.85
    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

if proc is None:
    make_audio(OUT + ".wav"); sys.exit()

dt = 1 / FPS
frame = 0
for name, dur in SCENES:
    nf = int(round(dur * FPS))
    for i in range(nf):
        t = i / FPS
        if name == "grill": img = sc_grill(t, dur, dt)
        else: img = globals()["sc_" + name](t, dur)
        # quick fade/flash between scenes
        edge = min(i, nf - 1 - i)
        if edge < 4 and not (name == "intro" and i < nf // 2):
            img = Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), (4 - edge) / 6)
        proc.stdin.write(img.tobytes())
        frame += 1
proc.stdin.close(); proc.wait()
print("frames", frame)
