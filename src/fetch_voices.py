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
for h in items:
    print(" -", h.get("history_item_id"), h.get("voice_name"), h.get("voice_id"), repr((h.get("text") or "")[:80]))

# L'historique de cette clé n'expose pas les textes : on utilise les identifiants connus (niveau 1 -> 7).
IDS = ["HsWOBcQEiExrziQDz3HE", "sYMoVpkkk7beu4e9uIZZ", "ALTQbSv6I8TGYbk3PN69", "hLlZsOy0rJBeWaO99Pfw",
       "r7H51STDRwXHwNmQ9HHi", "0xX93Ssp4qeWIU1MM5vy", "RNKg5l0LfQ78nGIRHP3h"]
known = {h["history_item_id"] for h in items}
for i, hid in enumerate(IDS, 1):
    if hid not in known:
        print(f"  attention: {hid} absent de l'historique")
    a = requests.get(f"https://api.elevenlabs.io/v1/history/{hid}/audio", headers=H, timeout=120)
    a.raise_for_status()
    path = os.path.join(OUT, f"{i:02d}.mp3")
    open(path, "wb").write(a.content)
    print(f"niveau {i} ({WANT[i-1][0]}): {len(a.content)} octets")
