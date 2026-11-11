"""Télécharge les 7 voix ElevenLabs d'un thème (par history_item_id, via l'API et la clé en secret).
usage: python src/fetch_voices.py OUT_DIR THEME"""
import json, os, sys, requests

OUT = sys.argv[1] if len(sys.argv) > 1 else "voices/raw"
THEME = sys.argv[2] if len(sys.argv) > 2 else "caca"
KEY = os.environ.get("ELEVENLABS_API_KEY")
if not KEY:
    sys.exit("ELEVENLABS_API_KEY manquant (secret GitHub)")
ids = json.load(open(os.path.join("themes", THEME, "theme.json")))["history_ids"]
assert len(ids) == 7, "il faut 7 history_ids"
os.makedirs(OUT, exist_ok=True)
H = {"xi-api-key": KEY}
for i, hid in enumerate(ids, 1):
    a = requests.get(f"https://api.elevenlabs.io/v1/history/{hid}/audio", headers=H, timeout=120)
    if a.status_code != 200:
        sys.exit(f"niveau {i}: {hid} -> HTTP {a.status_code} {a.text[:200]}")
    open(os.path.join(OUT, f"{i:02d}.mp3"), "wb").write(a.content)
    print(f"niveau {i}: {len(a.content)} octets")
