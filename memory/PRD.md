# Racontelle — Atelier Mémoire EHPAD (PRD)

## Problème initial (verbatim)
« Build a mobile app: Enregistrement de souvenirs vocaux de personnes âgées pendant un atelier de mémoire en EHPAD sur la base d'un enregistrement libre et 3 questions posées par jour par personne. Création de 10 profils avec prénom et enregistrement vocaux associés à la personne et datés. »

Clarifications utilisateur : offline-first avec stockage local (smartphones/tablettes) et synchronisation serveur temporaire ; UI très simplifiée et lisible pour les professionnels en atelier, selon la charte fournie (rose thé, sauge, brun mémoire, bleu encre) ; enregistrement libre ou réponse/skip à des questions guidées.

## Personas
- **Professionnel(le) EHPAD** (animateur/animatrice) : pilote l'atelier, gère les profils, lance les enregistrements. Besoin d'une interface très lisible, gros boutons, pas de navigation complexe.
- **Résident(e)** : raconte ses souvenirs à voix haute ; n'interagit pas directement avec l'app.
- **Famille / direction EHPAD** (futur) : écoute et partage des capsules privées.

## Exigences cœur (statiques)
1. Création de profils résidents (10 profils, prénom + consentement).
2. Enregistrement vocal libre par profil, daté.
3. 3 questions guidées par jour et par personne, avec option de réponse ou de skip.
4. Fonctionnement offline-first : enregistrement et sauvegarde locaux non bloqués si le serveur est injoignable ; synchronisation temporaire vers le serveur.
5. UI EHPAD : contraste élevé, grandes zones tactiles, charte rose thé / sauge / brun mémoire / bleu encre.

## Architecture
- **Frontend** : Expo / React Native (expo-router), `expo-audio` pour l'enregistrement, stockage local via `@/src/utils/storage`, thème dans `src/theme.ts`. UI principale dans `app/index.tsx` (Accueil, Création de profil, Atelier libre, Atelier questions, Archive).
- **Backend** : FastAPI (`/app/backend/server.py`), routes préfixées `/api` : `GET /api/questions`, `GET/POST /api/residents`, `GET/POST /api/capsules`, `GET /api/residents/{id}/capsules`, `DELETE /api/capsules/{id}`. MVP : données serveur en mémoire ; la persistance principale est locale sur l'appareil.
- **Tests** : `/app/backend/tests/test_racontelle_api.py` (pytest) — vert.

## Implémenté (sept. 2026)
- **Espace professionnel** : temps d'utilisation global de l'application et par personne (suivi local des segments fiche/atelier, attribution corrigée au profil sortant), nombre de souvenirs et durée d'audio par résident.
- **Conservation précieuse de l'audio** : chaque enregistrement quitte le cache système pour le stockage document permanent de l'appareil (`expo-file-system`), puis copie de sauvegarde dans Emergent Object Storage via `POST /api/capsules/{id}/audio`.
- **Transcription vocale** : Whisper (clé Emergent) via `POST /api/capsules/{id}/transcribe`, affichée dans la carte du souvenir.
- **Partage famille** : lien privé `GET /api/share/{token}` (page HTML aux couleurs Racontelle + lecteur audio + transcription), lien copié dans le presse-papiers.
- **Photo de profil** : sélection depuis la galerie (expo-image-picker, permissions contextuelles avec bouton « Ouvrir les réglages »), stockée localement, affichée dans les avatars.
- **Onde sonore animée** pendant l'enregistrement (react-native-reanimated).
- Charte graphique Racontelle appliquée : palette blanc doux #FFFFFF, rose thé #E7A7A5, sauge douce #B9C5B3, brun mémoire #A67C63, bleu encre doux #2F3E52 (`src/theme.ts` + `design_guidelines.json`).
- Typographies officielles chargées via `expo-font` : Allura (titres/accroches), Cormorant Garamond (textes), Montserrat (menus/boutons) — assets dans `frontend/assets/fonts/`.
- Logo officiel « Racontelle Care » affiché dans l'en-tête d'accueil (`assets/images/racontelle-logo.webp`) ; splash blanc ; app renommée « Racontelle ».
- Banque de questions extraite des documents fournis (thèmes Enfance, etc., avec marqueur « sensible »).
- Tests : 9/9 pytest backend (`test_audio_share_api.py`) + parcours frontend validés par le testing agent (itération 3).
- **Lecteur audio dans la fiche** : bouton lecture/pause par souvenir (testID `capsule-play-<id>`), dans la fiche et l'archive.
- **Export équipe soignante** : `GET /api/residents/{id}/export` génère un ZIP (audios + `souvenirs.txt` avec transcriptions) ; bouton « 1 · Extraire les souvenirs » (partage natif via expo-sharing, nouvel onglet sur web).
- **Retrait de profil sécurisé** : suppression douce (`DELETE /api/residents/{id}`, active=false, capsules conservées serveur) possible uniquement après export (trace `exports` dans l'état local) ; les fichiers audio locaux du résident sont effacés au retrait.
- Correctif : la synchronisation serveur (`refresh`) n'efface plus les compteurs de temps ni la trace des exports.
- Flux complet : Accueil → création de profil (max 10, modal scrollable, bouton accessible clavier) → atelier libre ou 3 questions/jour → enregistrement audio → archive datée par profil.
- Persistance locale JSON (profils + capsules), synchronisation serveur best-effort.
- `testID` sur les éléments interactifs ; réponses HTTP `201` conformes.
- Tests end-to-end validés par le testing agent (2 itérations) et script pytest backend vert.

## Backlog priorisé
- **P1** : Transcription automatique des enregistrements (ex. OpenAI Whisper via clé Emergent).
- **P1** : Partage privé de capsules aux familles.
- **P1** : Refactor `app/index.tsx` (~380 lignes) en écrans/composants séparés (`src/components`).
- **P2** : Segmentation des longs récits en chapitres.
- **P2** : Persistance serveur MongoDB complète (remplacer le stockage mémoire du MVP).
- **P2** : Architecture multi-établissements (multi-tenant).

## Prochaines tâches
1. Refactorer les écrans frontend en composants modulaires.
2. Brancher la transcription Whisper sur les capsules existantes.
3. Concevoir le flux de partage privé (lien sécurisé par capsule).
