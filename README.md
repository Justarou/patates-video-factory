# patates-video-factory

Vidéos TikTok « patates qui fusionnent » générées entièrement en code (2D, pymunk + PIL + FFmpeg).

- `assets/sprites/` : les 7 patates (PNG transparents)
- `src/fetch_voices.py` : télécharge les voix ElevenLabs via l'API (secret `ELEVENLABS_API_KEY`, droit « History » en lecture)
- `src/process_voices.py` : coupe les blancs, grave/basses/écho pour les gros niveaux
- `src/make_video.py` : simulation + rendu 1080x1920
- `src/mix_audio.py` : voix (volume croissant avec le niveau) + SFX + musique, assemblage
- Workflow : Actions → « Générer la vidéo patates » → Run workflow. Résultat : `output/patates.mp4` + artefact.
