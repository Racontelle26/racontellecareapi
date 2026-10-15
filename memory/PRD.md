# Racontelle Care — Atelier Mémoire EHPAD (PRD)

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
- **Transcription vocale UE** : Azure AI Speech STT en région France Central via `POST /api/capsules/{id}/transcribe`, avec conversion serveur M4A/WebM → WAV PCM 16 kHz mono ; seule la transcription finale est conservée.
- **Synthèse vocale UE** : Azure AI Speech TTS en région France Central via `POST /api/tts`, voix `fr-FR-AlainNeural` à vitesse `-5%`, sortie MP3 16 kHz 128 kbit/s. Le cache privé MongoDB `tts_cache` est conservé et indexé par texte + configuration vocale Azure.
- **Partage famille** : lien privé `GET /api/share/{token}` (page HTML aux couleurs Racontelle Care + lecteur audio + transcription), lien copié dans le presse-papiers.
- **Photo de profil** : sélection depuis la galerie (expo-image-picker, permissions contextuelles avec bouton « Ouvrir les réglages »), stockée localement, affichée dans les avatars.
- **Onde sonore animée** pendant l'enregistrement (react-native-reanimated).
- Charte graphique Racontelle Care appliquée : palette blanc doux #FFFFFF, rose thé #E7A7A5, sauge douce #B9C5B3, brun mémoire #A67C63, bleu encre doux #2F3E52 (`src/theme.ts` + `design_guidelines.json`).
- Typographies officielles chargées via `expo-font` : Allura (titres/accroches), Cormorant Garamond (textes), Montserrat (menus/boutons) — assets dans `frontend/assets/fonts/`.
- Logo officiel « Racontelle Care » affiché dans l'en-tête d'accueil (`assets/images/racontelle-logo.webp`) ; splash blanc ; application et métadonnées renommées « Racontelle Care ».
- Identité visuelle v1.0.2 : monogramme officiel « R » bleu encre, cercle végétal et point brun appliqué à l'icône Android/iOS, l'icône adaptative Android, le splash, le favicon, la connexion et l'accueil. Android `versionCode` 3 permet l'installation par-dessus l'APK précédent.
- Correctif icône native v1.0.3 : Android et iOS référencent explicitement des fichiers versionnés uniques (`racontelle-care-*-v4.png`) afin d'invalider l'ancien cache de build Emergent. Android `versionCode` 4 impose un nouvel APK distinct de celui affichant l'ancienne icône.
- Banque de questions extraite des documents fournis (thèmes Enfance, etc., avec marqueur « sensible »).
- Tests : 9/9 pytest backend (`test_audio_share_api.py`) + parcours frontend validés par le testing agent (itération 3).
- **Lecteur audio dans la fiche** : bouton lecture/pause par souvenir (testID `capsule-play-<id>`), dans la fiche et l'archive.
- **Export équipe soignante** : `GET /api/residents/{id}/export` génère un ZIP (audios + `souvenirs.txt` avec transcriptions) ; bouton « 1 · Extraire les souvenirs » (partage natif via expo-sharing, nouvel onglet sur web).
- **Retrait de profil sécurisé** : suppression douce (`DELETE /api/residents/{id}`, active=false, capsules conservées serveur) possible uniquement après export (trace `exports` dans l'état local) ; les fichiers audio locaux du résident sont effacés au retrait.
- Correctif : la synchronisation serveur (`refresh`) n'efface plus les compteurs de temps ni la trace des exports.
- **Impression du carnet** : `GET /api/residents/{id}/carnet` génère un PDF élégant (reportlab + polices Racontelle Care) des transcriptions du résident, prêt à offrir à la famille ; bouton « Imprimer le carnet (PDF) » sur la fiche.
- **Fusion des doublons** : `POST /api/residents/merge` rattache les souvenirs des fiches en double à la fiche conservée (suppression douce) ; section « Profils en double » dans l'espace professionnel avec modale de choix de la fiche à garder.
- **Choix du mode d'atelier** : sélecteur explicite « Question guidée » / « Enregistrement libre » en haut de l'atelier (masqué pendant l'enregistrement).
- **10 questions par jour** (au lieu de 3) : les questions déjà répondues par la personne sont mémorisées (`answered` dans l'état local) ; les questions passées ou non traitées sont reproposées lors des ateliers suivants. L'usager répond au nombre de questions qu'il souhaite.
- **Transcription automatique** : chaque souvenir synchronisé est transcrit sans action après la sauvegarde ; les souvenirs sans transcription (échec, hors connexion) sont retranscrits automatiquement en arrière-plan à chaque ouverture (max 5 par passage), visibles dans l'espace de chaque résident avec mention « Transcription automatique en cours… ». Le bouton manuel « Retranscrire » reste disponible.
- Tests itération 5 : 13/13 pytest backend + parcours frontend validés (fusion, carnet PDF, sélecteur de mode) ; correctif du crash archive (props non déstructurées) appliqué par le testing agent.
- **Minutage réel** (it. 7-8) : chrono basé horloge avec pause/reprise, durée exacte figée à l'arrêt et sauvegardée, minutage précis dans l'espace pro ; réécoute avant sauvegarde corrigée (session audio iOS).
- **Création de profil fiable** (it. 8) : bouton « Créer le profil » collé au clavier (KeyboardAwareScrollView + KeyboardStickyView), création via touche « done », message si prénom vide.
- **Renommage** (it. 8) : profils (clic sur le nom, `PATCH /api/residents/{id}`) et souvenirs sur le vif (`PATCH /api/capsules/{id}`), avec rattachement d'un souvenir à un profil (`PATCH /api/capsules/{id}/assign`, modale edit-capsule).
- **Archive « Mes souvenirs »** (it. 9) : la vue « Tous » masque les souvenirs libres déjà réattribués (visibles dans la fiche du membre et son filtre).
- **Réponses guidées par profil** : la fiche de chaque personne distingue désormais clairement toutes ses réponses aux questions de ses souvenirs libres ; la question, l'audio et la transcription restent réunis dans la même carte.
- **Sécurité multi-établissements** : authentification professionnelle email/mot de passe, mots de passe Argon2id, access JWT de 15 minutes et refresh token rotatif/révocable de 30 jours. Chaque inscription crée un établissement isolé et un compte Administrateur.
- **Rôles Administrateur / Membre** : les membres peuvent mener les ateliers et consulter les données de leur établissement ; suppressions, fusion, exports, carnets PDF, révocation des partages et création de membres sont réservés aux administrateurs.
- **Isolation stricte** : toutes les requêtes MongoDB résidents, capsules, exports, carnets, audios et partages sont filtrées côté serveur par `tenant_id`. Les données historiques sans établissement sont placées en quarantaine et ne sont exposées à aucun nouveau compte.
- **Sessions mobiles sécurisées** : jetons et PIN professionnel utilisent SecureStore sur iOS/Android. Sur le web, le refresh token reste dans un cookie HttpOnly/Secure/SameSite et les secrets d'interface restent uniquement en mémoire.
- **Partages familiaux contrôlés** : liens aléatoires valables 30 jours, un seul lien actif par capsule, expiration MongoDB TTL et révocation immédiate par un administrateur.
- **Quotas anti-abus** : limites atomiques quotidiennes par utilisateur de 30 transcriptions, 100 lectures TTS et 100 envois audio, avec réponses HTTP 429 et messages locaux préservant toujours l'enregistrement.
- **CORS strict** : seule l'origine déclarée dans `CORS_ORIGINS` est autorisée ; les origines inconnues ne reçoivent aucun en-tête d'autorisation CORS.
- Tests sécurité et régression backend : **45/45 tests réussis**, dont accès anonyme refusé, étanchéité entre deux établissements, permissions membre, rotation refresh, quotas et révocation de partage.
- **Chronométrage d'utilisation réel** : le temps total compte chaque milliseconde où l'application est au premier plan. Le temps par résident compte uniquement la fiche et l'atelier de cette personne. Aucun seuil de 3 secondes ni arrondi n'est appliqué ; l'affichage avance en direct chaque seconde et les compteurs sont persistés toutes les 10 secondes. L'horloge monotone évite les erreurs liées au changement d'heure du téléphone et les anciennes durées en secondes sont migrées sans perte.
- **Ouverture automatique mémorisée** : après une première connexion, l'identité non sensible de l'établissement est mémorisée. Les lancements suivants ouvrent directement les données locales du bon établissement sans requête, refresh ou validation serveur au démarrage. Les jetons restent dans SecureStore sur mobile et ne sont jamais persistés sur le web ; la validation serveur intervient uniquement lors d'une action nécessitant le réseau.
- **Reconnexion lisible** : lorsque la session expire pendant une action serveur, l'adresse email reste préremplie et le champ mot de passe propose un bouton œil accessible pour afficher ou masquer la saisie. Le mot de passe n'est jamais mémorisé.
- **Procédure opérateur de récupération** : `backend/scripts/reset_user_password.py` permet une réinitialisation idempotente depuis le terminal privé Railway, avec saisie masquée, hash pwdlib identique au login, révocation des sessions, nettoyage des blocages et audit sans secret. Elle reste disponible comme solution de secours indépendante de l’email.
- **Récupération par email Resend** : le backend appelle directement l’API officielle Resend avec l’expéditeur vérifié `no-reply@racontellecare.com`, un lien HTTPS vers l’écran « Nouveau mot de passe » et un code à usage unique. La clé reste uniquement côté serveur ; le destinataire, l’objet et le modèle ne sont jamais fournis par le client.
- **Déploiement Resend vérifié** : la révision incluant l’API Resend officielle est active sur Railway ; l’aperçu public réel appelle cette API et reçoit le nouveau contrat « un lien et un code ». La livraison réelle reste conditionnée à la présence de `RESEND_API_KEY`, `RESEND_FROM_EMAIL` et `PASSWORD_RESET_URL` dans Railway.
- **Backend mobile Railway** : le frontend utilise `https://racontellecareapi-production.up.railway.app` via `EXPO_PUBLIC_BACKEND_URL`; toutes les routes continuent d'ajouter le préfixe `/api` côté client.
- **Déploiement backend déterministe** : Railway construit désormais le `Dockerfile` racine, installe explicitement `backend/requirements.txt` (dont uvicorn), conserve `ffmpeg` pour Azure Speech et démarre FastAPI strictement sur `$PORT`. Aucun `EXPOSE`, port hardcodé ou port de repli n'est utilisé ; l'image échoue clairement si Railway ne fournit pas `PORT`. Les fichiers `.env`, tests et données locales sont exclus de l'image.
- **Recette totale après incident Railway** : API publique Railway stable (5× HTTP 200, aucun 502), CORS/en-têtes/auth anonyme conformes, routes forgot/reset déployées, 46 tests backend réussis, Expo Doctor 20/20, lint/TypeScript/export web réussis. Le frontend appelle de nouveau Railway directement. Le mode local permet maintenant de supprimer proprement un profil local après protection par PIN.
- Flux complet : Accueil → création de profil (max 10, modal scrollable, bouton accessible clavier) → atelier libre ou 10 questions/jour → enregistrement audio → archive datée par profil.
- Persistance locale JSON (profils + capsules), synchronisation serveur best-effort.
- `testID` sur les éléments interactifs ; réponses HTTP `201` conformes.
- Tests end-to-end validés par le testing agent (2 itérations) et script pytest backend vert.

## Mise à niveau bêta (25 sept. 2026) — cahier des charges Bêta Test du 15/09/2026
Détail critère par critère : `docs/CONFORMITE_CAHIER_DES_CHARGES.md`.
- **Corrections critiques** : plus aucune perte d'audio au retrait d'un profil (export vérifié, retrait bloqué tant qu'un audio n'est pas « Sauvegardé ») ; types audio contrôlés + `nosniff` + CSP sur les liens de partage (faille de vol de session fermée) ; un membre ne peut plus retirer/réactiver un profil par `PATCH` ; `audio_base64` n'est plus stocké ; cache TTS privé.
- **Dépendances vocales** : les SDK et modèles OpenAI/LiteLLM ont été retirés. L'image Docker Railway installe `ffmpeg` pour normaliser les fichiers avant envoi à Azure France Central ; la clé Azure reste uniquement dans les variables du backend.
- **Hors connexion réel** : file d'attente rejouée automatiquement (profils, renommages, consentements, retraits, fusions, souvenirs, classements, copies audio) ; indicateur « En attente d'envoi » / « Sauvegardé ».
- **Périmètre bêta** : 5 profils max ; 400 questions (annexe A) embarquées et sur le serveur, thèmes sensibles désactivés par défaut ; parcours résident → thème / Question surprise → question → « Une autre question » → enregistrer → « Capsule sauvegardée » ; rubrique « À classer » ; date + heure ; consentement à 3 états journalisé ; champs initiale/unité.
- **Quiz « Qui a dit ça ? »** (`backend/quiz.py`) : citations + musique, import CSV/JSON (annexe B), droits contrôlés, score de session facultatif.
- **Pilotage** (`backend/beta.py`) : interrupteurs de fonctions par établissement (transcription, partage famille, carnet PDF désactivés par défaut), journal d'audit, retours testeurs avec version, événements et indicateurs exportables en CSV.
- **Récupération du mot de passe** : code email 30 min / 5 essais, sessions révoquées ; mot de passe temporaire défini par l'admin.
- **Refactor** : `app/index.tsx` réduit à l'orchestration ; écrans dans `src/screens`, fenêtres dans `src/components/modals.tsx`, données dans `src/hooks`.
- **Charte** : bleu encre #2F3E52 couleur prioritaire de Racontelle Care.

## Backlog priorisé
- **P0** : Ajouter `RESEND_API_KEY`, `RESEND_FROM_EMAIL=no-reply@racontellecare.com` et `PASSWORD_RESET_URL` aux variables Railway puis tester une livraison réelle ; créer un compte Railway de recette dédié pour automatiser login, synchronisation et Azure en production ; importer des extraits musicaux autorisés.
- **Azure Railway actif** : l’utilisateur confirme le fonctionnement des flux STT/TTS Azure France Central après redéploiement ; aucun fallback simulé n’est utilisé.
- **P1** : Hébergement UE, sauvegardes automatiques, environnements recette/bêta, builds iOS/Android privés, suivi des crashs.
- **P1** : Message « niveau sonore insuffisant » (mesure du volume pendant l'enregistrement).
- **P2** : Base relationnelle (PostgreSQL) demandée par le cahier des charges ; segmentation des longs récits ; invitation par email.
