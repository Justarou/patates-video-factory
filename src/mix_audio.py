"""Mixe voix (volume croissant avec le niveau), SFX et musique synthétiques, puis assemble avec la vidéo."""
import json, os, subprocess, sys
import numpy as np
import soundfile as sf

BUILD = sys.argv[1] if len(sys.argv) > 1 else "build"
VOICES = sys.argv[2] if len(sys.argv) > 2 else "voices/final"
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(BUILD, "patates.mp4")
SR = 44100
ev = json.load(open(os.path.join(BUILD, "events.json")))
dur = ev["duration"] + 1.0
mix = np.zeros(int(dur * SR), dtype=np.float32)


def put(sig, t, gain=1.0):
    i = int(t * SR)
    if i >= len(mix):
        return
    n = min(len(sig), len(mix) - i)
    mix[i:i + n] += sig[:n] * gain


def env_sine(f0, f1, length, decay=6.0, vol=1.0):
    n = int(length * SR); t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (t / length)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-decay * t) * vol).astype(np.float32)


rng = np.random.default_rng(3)
# --- musique : boucle simple kick / hat / basse, 124 bpm
bpm = 124; beat = 60 / bpm
kick = env_sine(150, 45, 0.25, 12, 0.9)
hat = (rng.standard_normal(int(0.05 * SR)) * np.exp(-60 * np.arange(int(0.05 * SR)) / SR)).astype(np.float32) * 0.25
notes = [55, 55, 65.4, 49]
t = 0.0; k = 0
while t < dur:
    put(kick, t, 0.5)
    put(hat, t + beat / 2, 0.35)
    nf = notes[(k // 4) % 4]
    put(env_sine(nf, nf, beat * 0.9, 3.5, 0.5) * 0.6, t, 0.5)
    t += beat; k += 1

# --- SFX : pop à chaque lâcher, boing à chaque fusion
for e in ev["events"]:
    if e["kind"] == "drop":
        put(env_sine(300, 140, 0.12, 25, 0.5), e["t"], 0.5)
    else:
        lvl = e["level"]
        put(env_sine(260 - lvl * 22, 700 - lvl * 40, 0.28, 8, 0.7), e["t"], 0.6 + 0.05 * lvl)
        if lvl >= 4:
            put(env_sine(90, 38, 0.9, 4, 1.0), e["t"], 0.5 + 0.1 * (lvl - 4))
boss = ev["boss_t"]
put(env_sine(70, 25, 2.5, 1.6, 1.0), boss, 1.0)                       # grosse bombe
n = int(1.5 * SR)
put((rng.standard_normal(n) * np.exp(-3 * np.arange(n) / SR) * 0.4).astype(np.float32), boss, 0.8)

music_sfx = mix.copy(); mix[:] = 0
mix += music_sfx * 0.55

# --- voix : plus on monte, plus c'est fort (-12 dB niveau 1 -> +4 dB boss)
for a in ev["announcements"]:
    lvl = a["level"]
    v, sr = sf.read(os.path.join(VOICES, f"{lvl + 1:02d}.wav"), dtype="float32")
    if v.ndim > 1:
        v = v.mean(axis=1)
    gain_db = -12.0 + 2.7 * lvl
    put(v, a["t"], 10 ** (gain_db / 20))

sf.write(os.path.join(BUILD, "mix_raw.wav"), mix, SR)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, "mix_raw.wav"),
                "-af", "alimiter=limit=0.93:attack=3:release=60,loudnorm=I=-14:TP=-1.0:LRA=9",
                os.path.join(BUILD, "mix.wav")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, "video_silent.mp4"),
                "-i", os.path.join(BUILD, "mix.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", OUT], check=True)
print("ok ->", OUT)
