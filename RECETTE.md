# Recette : vidéo « patates qui fusionnent » (style Suika)

Ce qui change d'une vidéo à l'autre : **le style des 7 patates** et **les 7 noms**. Tout le reste est fixe.

## Étapes (dans cet ordre, validation d'Aaron entre chaque)
1. **Noms + thème** : 7 niveaux, du plus petit au boss. Noms drôles, absurdes, jamais de vrais politiques (inventer).
2. **Sprites** : 7 PNG transparents 512x512, dessinés en code (PIL), pas de génération IA d'image. Même patate de base (yeux, bouche), un accessoire/déco par niveau, le niveau 7 = boss énorme avec lueur. Sauvés dans `assets/sprites/01_...` à `07_...`.
2b. Planche contact envoyée pour validation.
3. **Voix ElevenLabs** (modèle `eleven_v4`, tags `[...]`) : une voix DIFFÉRENTE par niveau, de plus en plus grave/lente/giga chad. Niveau 1 = aiguë « chipmunk », boss = la plus grave possible. Générer UNE à la fois, `generations_count=1`, vérifier chaque sortie, ne jamais relancer à l'aveugle (ça coûte ~1 centime/prise). Texte = « La patate X ! » en un seul bloc, sans pause entre « patate » et le nom.
4. **Validation** des visuels et des voix par Aaron.
5. **Vidéo** : générée en code par le workflow GitHub (jamais Higgsfield, jamais HyperFrames).

## Règles de la vidéo (validées)
- Format 1080x1920, 30 fps, MP4.
- Fond noir uni. Ballon rond (cercle) avec contour arc-en-ciel lumineux, goulot en haut formé de **deux traits blancs lumineux verticaux** montant jusqu'en haut de l'écran.
- Sous le ballon : `SCORE: N` puis 7 pastilles rondes (icône du niveau, ou « ? » tant que non découvert).
- **Aucun sous-titre, aucun texte de nom, aucune phrase d'accroche, aucune musique, aucun bruitage.** Seulement les voix.
- **Seules des patates niveau 1 tombent**, du haut de l'écran (hors champ), à travers le goulot, **une à la fois** : la suivante part dès que la précédente a dépassé la fin des traits blancs. Chute légèrement non droite (balancement doux, 18-38 px) sans jamais toucher les parois du tube.
- Une fois dans le ballon : physique pymunk, rebonds **faibles** (élasticité ~0,3 patate / 0,5 paroi), pas d'aimant ni d'attraction : **seul un choc entre deux patates du même niveau fait monter d'un niveau**. Les patates ne doivent jamais remonter.
- Fusion → nouvelle patate au milieu, petit « pop » visuel, anneau, tremblement d'écran croissant avec le niveau ; boss = flash blanc + gros tremblement.
- 7 niveaux, boss = niveau 7 (rayons collision 56, 72, 90, 112, 138, 168, 198 px).
- La graine de simulation est choisie parmi 60 : on garde celle où le boss arrive le plus tôt (~49 s, vidéo ~54 s).
- **Voix** : chaque fusion déclenche la voix du niveau obtenu (intro : voix niveau 1). **La voix de la patate qui vient de naître coupe toutes les autres voix en cours** (fondu de 30 ms) : c'est la seule qu'on entend. Si une voix d'un niveau plus haut parle encore, une fusion de niveau plus bas ne la coupe pas. Volume croissant avec le niveau : -9 dB au niveau 1, +2,5 dB par niveau (≈ +6 dB au boss). Niveaux 5-7 : traitement grave (pitch, basses, écho) dans `process_voices.py`. Début/fin de chaque voix coupés pour que le nom s'enchaîne sans blanc.

## Technique
- Dépôt : `Justarou/patates-video-factory` (public). Secret `ELEVENLABS_API_KEY` (droit History en lecture).
- Workflow `Générer la vidéo patates` : `fetch_voices.py` → `process_voices.py` → `make_video.py` → `mix_audio.py` → `output/patates.mp4` (~2-3 min). Lancer avec `gh workflow run video.yml --ref main`.
- **L'API d'historique ne donne pas les textes** : les voix sont récupérées par `history_item_id`. Pour une nouvelle vidéo, noter le `historyItemId` de chaque génération (dans `product_link` du résultat) et mettre à jour `IDS` dans `src/fetch_voices.py`.
- Pour un nouveau thème : remplacer les 7 PNG dans `assets/sprites/`, mettre à jour `NAMES`, `SHORT`, `SPRITE_FILES` et le tableau `WANT`/`IDS` des voix, puis lancer le workflow.
- Les liens de téléchargement ElevenLabs sont bloqués depuis l'environnement de Claude : tout passe par le workflow.

## Préférences d'Aaron
- Parle français, voix-to-text : interpréter l'intention sans redemander pour des fautes.
- Ne pas dépenser de crédits ElevenLabs sans son accord ; pas de génération tant qu'il n'a pas validé l'étape précédente.
- Livrer chaque version de la vidéo avec le fichier envoyé directement.
