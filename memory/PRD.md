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

## Ajouts (2026-06, itération 4)
- Photo par souvenir : ajout optionnel d'une photo pendant l'enregistrement et sur un souvenir existant (galerie ou appareil photo, permissions gérées). Affichage en vignette dans l'album et en image d'en-tête du détail. Stockage privé (Object Storage), flux sécurisé par token.
- Livre PDF : assemblage des chapitres (couverture Racontelle + chapitres + album photo illustré) en un PDF partageable/téléchargeable (expo-print + expo-sharing).
- Bouton « Sur le vif » : bouton flottant sur l'accueil pour lancer instantanément un enregistrement libre (sans question).
- Tests itération 4 : 14/14 backend OK (endpoints photo + isolation), présences frontend vérifiées.

## Correctifs et vérification générale (2026-09, itération 5)
- Réponses vocales fiabilisées sur les trois entrées : question du jour, question thématique et « Sur le vif ».
- Préécoute explicite avant sauvegarde : lecture/pause, recommencer, session audio basculée du micro vers la lecture.
- Sauvegarde renforcée : narrateur garanti, durée minimale cohérente, erreurs API lisibles et confirmation par ouverture du souvenir créé.
- Cache privé annulé et vidé à la déconnexion/reconnexion pour éviter requêtes 401 résiduelles et données d’un compte précédent.
- Livre stabilisé : chapitre ajouté immédiatement à la liste, erreur visible, états chargement/erreur sur la lecture, bouton PDF confirmé.
- Vérification générale : 11/11 tests backend et parcours mobiles auth, questions, album, audio, photos, profil, membres, invitations, feedback, livre et déconnexion validés.
- E-mail géré vérifié sur l’adresse de validation du fournisseur : requête acceptée (HTTP 202).

## Profils familiaux et fiches membres (2026-09, itérations 6–7)
- Création initiale du cercle avec le créateur et jusqu’à trois profils familiaux sans e-mail.
- Création directe limitée à quatre profils ; invitation par e-mail à partir du cinquième membre.
- Profils sans compte modifiables et supprimables depuis « Membres » ; suppression bloquée tant que des souvenirs leur sont rattachés.
- Actions « Renvoyer » et « Annuler » des invitations liées fiablement par `member_id`.
- Page « À propos de Racontelle » accessible par le logo, avec texte de présentation et contact `laracontelle@gmail.com`.
- Souvenirs « Sur le vif » nommables avant sauvegarde, puis renommables et réattribuables à un autre profil familial.
- Onglet Profil enrichi avec tous les membres actifs : prénom, lien familial, nombre de souvenirs et temps enregistré.
- Fiche membre dédiée avec statistiques, durée totale, état vide et liste chronologique ouvrant chaque souvenir.
- Statistiques calculées par agrégation MongoDB, isolées par cercle et limitées aux souvenirs sauvegardés.
- Recette : itération 6 backend 10/10 ; itération 7 backend 3/3 et parcours mobiles validés, y compris durées secondes/minutes/heures et noms longs.

## Backlog (prioritized)
- P2 : Réponse texte/photo à une question ; carte postale souvenir PDF ; capsule temporelle.
- P2 : Export des événements CSV (mesure bêta) via endpoint admin.
- P2 : Avatar évolutif / badges non compétitifs.
- P3 : audio 401 propre (au lieu de 422) sans token ; nettoyage warnings RN-web (pointerEvents/shadow).

## Next tasks
- Recueillir les retours bêta des familles.
- Vérifier la délivrabilité des invitations sur quelques adresses familiales réelles pendant la bêta.
