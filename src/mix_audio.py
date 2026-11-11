"""Mixe voix (volume croissant avec le niveau) et SFX synthétiques (pas de musique), puis assemble avec la vidéo."""
import json, os, subprocess, sys
import numpy as np
import soundfile as sf

BUILD = sys.argv[1] if len(sys.argv) > 1 else "build"
VOICES = sys.argv[2] if len(sys.argv) > 2 else "voices/final"
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(BUILD, "patates.mp4")
SR = 44100
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
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

music_sfx = mix.copy(); mix[:] = 0
mix += music_sfx * 0.7

# --- voix : plus on monte, plus c'est fort (-9 dB niveau 1 -> ~+6 dB boss)
# Règle : la voix de la patate qui vient de naître coupe toutes les autres voix en cours
# (sauf si une voix d'un niveau plus haut parle encore : on protège le plus gros nom).
voices = {}
for lvl in range(7):
    v, sr = sf.read(os.path.join(VOICES, f"{lvl + 1:02d}.wav"), dtype="float32")
    voices[lvl] = v.mean(axis=1) if v.ndim > 1 else v
plan = []                                   # {t, level, end}
cands = [(0.7, 0)] + [(e["t"], e["level"]) for e in ev["events"] if e["kind"] == "merge"]
for t0, lvl in cands:
    end = t0 + len(voices[lvl]) / SR
    if plan and t0 < plan[-1]["end"]:
        if lvl >= plan[-1]["level"]:
            plan[-1]["end"] = t0            # on coupe la voix précédente
        else:
            continue                        # un plus gros nom parle encore : on ne le coupe pas
    plan.append({"t": t0, "level": lvl, "end": end})
FADE = int(0.03 * SR)
for a in plan:
    v = voices[a["level"]].copy()
    n = min(len(v), int((a["end"] - a["t"]) * SR))
    v = v[:n]
    if n < len(voices[a["level"]]) and n > FADE:
        v[-FADE:] *= np.linspace(1, 0, FADE)  # fondu très court pour éviter le clic
    gain_db = -9.0 + 2.5 * a["level"]
    put(v, a["t"], 10 ** (gain_db / 20))
print(len(plan), "voix jouées,", sum(1 for a in plan if a["end"] < a["t"] + len(voices[a["level"]]) / SR - 0.01), "coupées")

pk = float(np.max(np.abs(mix))) or 1.0
mix *= 1.6 / pk if pk < 1.6 else 1.0   # niveau global sans écraser les écarts entre niveaux
sf.write(os.path.join(BUILD, "mix_raw.wav"), mix, SR)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, "mix_raw.wav"),
                "-af", "alimiter=limit=0.93:attack=3:release=60",
                os.path.join(BUILD, "mix.wav")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(BUILD, "video_silent.mp4"),
                "-i", os.path.join(BUILD, "mix.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", OUT], check=True)
print("ok ->", OUT)
