"""Traite chaque voix : coupe les blancs (le nom s'enchaîne sans pause), grave/basses pour les gros niveaux."""
import glob, os, subprocess, sys

RAW = sys.argv[1] if len(sys.argv) > 1 else "voices/raw"
OUT = sys.argv[2] if len(sys.argv) > 2 else "voices/final"
os.makedirs(OUT, exist_ok=True)

_S = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
TRIM = f"{_S},areverse,{_S},areverse,"   # coupe seulement début et fin
# (hauteur, tempo, basses dB, écho)
FX = {
    1: "", 2: "", 3: "",
    4: "rubberband=pitch=0.94:tempo=0.96,bass=g=3:f=120:w=0.8,",
    5: "rubberband=pitch=0.90:tempo=0.92,bass=g=5:f=110:w=0.8,",
    6: "rubberband=pitch=0.86:tempo=0.90,bass=g=7:f=100:w=0.8,",
    7: "rubberband=pitch=0.72:tempo=0.85,bass=g=11:f=90:w=0.8,"
       "aecho=0.8:0.55:70|140:0.28|0.15,",
}
for lvl in range(1, 8):
    src = next(iter(glob.glob(os.path.join(RAW, f"{lvl:02d}.*"))), None)
    if not src:
        sys.exit(f"voix {lvl} manquante dans {RAW}")
    af = TRIM + FX[lvl] + "acompressor=threshold=-18dB:ratio=4:attack=5:release=120," \
         "loudnorm=I=-16:TP=-1.5:LRA=7"
    dst = os.path.join(OUT, f"{lvl:02d}.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-af", af,
                    "-ar", "44100", "-ac", "1", dst], check=True)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", dst], capture_output=True, text=True).stdout.strip()
    print(f"voix {lvl}: {d}s")
