"""Télécharge les 7 voix ElevenLabs depuis l'historique du compte (API, clé en secret)."""
import os, sys, requests

KEY = os.environ.get("ELEVENLABS_API_KEY")
OUT = sys.argv[1] if len(sys.argv) > 1 else "voices/raw"
os.makedirs(OUT, exist_ok=True)

# niveau -> (phrase recherchée, voice_id attendu)
WANT = [
    ("patate chips",     "fsYODoWLWYJ5ai6CAN3M"),  # Tony
    ("patate nuggets",   "1lNxvBaIR57JBl6dRELm"),  # Victor
    ("patate raclette",  "j9RedbMRSNQ74PyikQwD"),  # Louis
    ("patate kebab",     "30MA7zYVNHAmlXqFhk8P"),  # Julien
    ("sauce blanche",    "ULDw9NhSQODAHXxn70tR"),  # Lucas
    ("buffet",           "wQjKP9DkO6pDLKdaqFn6"),  # Bass
    ("fondue savoyarde", "FmOMKTYDTzzmpxukR0kC"),  # Emilio
]

if not KEY:
    sys.exit("ELEVENLABS_API_KEY manquant (secret GitHub)")
H = {"xi-api-key": KEY}

items, token = [], None
for _ in range(10):
    p = {"page_size": 1000}
    if token:
        p["start_after_history_item_id"] = token
    r = requests.get("https://api.elevenlabs.io/v1/history", headers=H, params=p, timeout=60)
    if r.status_code != 200:
        sys.exit(f"Historique inaccessible ({r.status_code}): {r.text[:300]} -> la clé doit avoir le droit 'History' en lecture")
    d = r.json()
    items += d.get("history", [])
    if not d.get("has_more"):
        break
    token = d.get("last_history_item_id")
print(len(items), "éléments d'historique")

for i, (phrase, vid) in enumerate(WANT, 1):
    cands = [h for h in items if phrase in (h.get("text") or "").lower() and h.get("voice_id") == vid]
    if not cands:
        cands = [h for h in items if phrase in (h.get("text") or "").lower()]
    if not cands:
        sys.exit(f"Voix niveau {i} introuvable dans l'historique (phrase '{phrase}')")
    h = max(cands, key=lambda x: x.get("date_unix", 0))
    a = requests.get(f"https://api.elevenlabs.io/v1/history/{h['history_item_id']}/audio", headers=H, timeout=120)
    a.raise_for_status()
    path = os.path.join(OUT, f"{i:02d}.mp3")
    open(path, "wb").write(a.content)
    print(f"niveau {i}: {h.get('voice_name')} {len(a.content)} octets <- {h.get('text')!r}")
