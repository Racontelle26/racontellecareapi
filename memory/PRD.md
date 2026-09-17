# Racontelle Family — PRD

## Problem statement (original, verbatim)
« Créer une application mobile : enregistrement des souvenirs vocaux d'une famille dans le but de fabriquer un livre romancé avec les souvenirs collectés. Les membres de la famille en seraient alors les personnages principaux. »

Trois cahiers des charges fournis (Beta test, MVP technique chiffrable, V7 rituels 400 questions).

## User choices
- Périmètre : **MVP complet** du cahier des charges.
- Auth : **email + mot de passe** (JWT).
- Livre romancé (IA) : **plus tard**.
- Design : univers **Racontelle** (rose poudré, élégant, script chaleureux).
- **Pas de limite stricte** de membres.
- Nouveautés demandées : **arbre qui grandit** avec les souvenirs (progression visible), **jusqu'à 3 questions par jour**, souvenirs « précieusement enregistrés et archivés ».

## Architecture
- Frontend : Expo (React Native) + expo-router, react-query, expo-audio, react-native-svg (arbre), phosphor icons, Cormorant Garamond + DM Sans.
- Backend : FastAPI + Motor (MongoDB). JWT (PyJWT + passlib/bcrypt).
- Stockage audio : **Emergent Object Storage** (privé, streaming via backend + token).
- Emails transactionnels : **Emergent Resend** (invitations + rappel question du jour).
- Thème : /app/frontend/src/theme.ts (tokens du design_guidelines.json).

## Personas
- Le créateur du cercle (souvent un parent/enfant adulte) qui invite la famille.
- Les proches (grands-parents, parents, enfants) qui racontent leurs souvenirs à voix haute.

## Core requirements (static)
- Cercle familial privé, invitations par e-mail + code, un compte = un cercle.
- Banque de 400 questions par thèmes (2 thèmes sensibles masqués/inactifs).
- Enregistrement vocal guidé par une question, album vocal privé, lecture, suppression douce.
- Jusqu'à 3 questions du jour par cercle/jour, états par membre (viewed/skipped/answered).
- Arbre des souvenirs qui grandit selon le nombre de capsules.
- Feedback bêta, préférences (couleur, e-mail quotidien).

## Implemented (2026-06)
- Auth email/mot de passe + réinitialisation par code e-mail (JWT 30j).
- Création / rejoindre un cercle, membres, invitations (créer/renvoyer/révoquer), acceptation par code.
- 400 questions FR authentiques seedées, thèmes, filtre, question surprise, thèmes sensibles cachés.
- Moteur question du jour (jusqu'à 3/cercle/jour, anti-répétition, variation de thème) + états membre.
- Capsules audio : upload multipart → object storage, album (filtres narrateur), détail + lecteur, suppression douce, streaming sécurisé par token, isolation par cercle.
- Arbre SVG évolutif (10 niveaux) + barre de progression sur l'accueil.
- Onglets Accueil / Raconter / Album / Profil, écran d'enregistrement (permissions micro), feedback.
- Emails invitation + réinitialisation (gate de sécurité du playbook).
- Tests : 23/23 backend pytest OK, flux frontend vérifiés.

## Ajouts (2026-06, itération 3)
- Transcription automatique des souvenirs vocaux (OpenAI Whisper via clé universelle) en tâche de fond ; statut visible dans le détail (en cours / fait / relancer).
- Livre romancé : génération d'un chapitre chaleureux et littéraire tissant les souvenirs, chaque proche en personnage (Claude Sonnet 5). Écrans /book (liste + génération + statut) et /book/[id] (lecture), CTA sur l'accueil.
- Recherche dans l'album par personne + thème + mots-clés (question, titre, thème, narrateur, transcription).
- Tests itération 3 : 12/12 backend OK, flux frontend vérifiés (isolation par cercle confirmée sur les chapitres).

## Backlog (prioritized)
- P1 : Génération IA du "livre romancé" (chapitre à partir des souvenirs) — demandé pour plus tard.
- P1 : Transcription audio (préparer le livre) + recherche dans l'album.
- P2 : Réponse texte/photo à une question ; carte postale souvenir PDF ; capsule temporelle.
- P2 : Export des événements CSV (mesure bêta) via endpoint admin.
- P2 : Avatar évolutif / badges non compétitifs.
- P3 : audio 401 propre (au lieu de 422) sans token ; nettoyage warnings RN-web (pointerEvents/shadow).

## Next tasks
- Recueillir les retours bêta des familles.
- Préparer l'intégration IA du livre romancé quand l'utilisateur le décidera.
