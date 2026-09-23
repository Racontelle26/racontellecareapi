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
- **Transcription vocale** : Whisper (clé Emergent) via `POST /api/capsules/{id}/transcribe`, affichée dans la carte du souvenir.
- **Partage famille** : lien privé `GET /api/share/{token}` (page HTML aux couleurs Racontelle Care + lecteur audio + transcription), lien copié dans le presse-papiers.
- **Photo de profil** : sélection depuis la galerie (expo-image-picker, permissions contextuelles avec bouton « Ouvrir les réglages »), stockée localement, affichée dans les avatars.
- **Onde sonore animée** pendant l'enregistrement (react-native-reanimated).
- Charte graphique Racontelle Care appliquée : palette blanc doux #FFFFFF, rose thé #E7A7A5, sauge douce #B9C5B3, brun mémoire #A67C63, bleu encre doux #2F3E52 (`src/theme.ts` + `design_guidelines.json`).
- Typographies officielles chargées via `expo-font` : Allura (titres/accroches), Cormorant Garamond (textes), Montserrat (menus/boutons) — assets dans `frontend/assets/fonts/`.
- Logo officiel « Racontelle Care » affiché dans l'en-tête d'accueil (`assets/images/racontelle-logo.webp`) ; splash blanc ; application et métadonnées renommées « Racontelle Care ».
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
- Flux complet : Accueil → création de profil (max 10, modal scrollable, bouton accessible clavier) → atelier libre ou 10 questions/jour → enregistrement audio → archive datée par profil.
- Persistance locale JSON (profils + capsules), synchronisation serveur best-effort.
- `testID` sur les éléments interactifs ; réponses HTTP `201` conformes.
- Tests end-to-end validés par le testing agent (2 itérations) et script pytest backend vert.

## Backlog priorisé
- **P0 — Intégration externe** : la clé gérée actuelle fonctionne pour Object Storage mais ne possède pas l'autorisation `whisper-1`. La transcription automatique reste indisponible jusqu'à l'activation de l'entitlement STT/Whisper ; aucun fallback simulé n'est utilisé.
- **P1** : Refactor `app/index.tsx` (> 1 300 lignes) en écrans/composants séparés (`src/components`).
- **P2** : Segmentation des longs récits en chapitres.
- **P2** : Invitation par email et réinitialisation autonome du mot de passe.

## Prochaines tâches
1. Refactorer les écrans frontend en composants modulaires.
2. Ajouter l'invitation par email et la récupération de mot de passe.
3. Concevoir un journal d'audit administrateur des opérations sensibles.
