# Racontelle Care — mémoire du projet

Application d'atelier mémoire en EHPAD : enregistrement des souvenirs racontés par les
résidents. Propriétaire : Racontelle (GitHub `Racontelle26`). Répondre en français, simplement,
sans condescendance : l'utilisatrice n'est pas développeuse et veut des étapes courtes et sûres.
État détaillé et historique : `docs/POINT_AVANCEMENT.md`. Produit : `memory/PRD.md`.

## À faire le 18/10/2026 (dans cet ordre)

Fait le 17/10 : enregistrement jusqu'au bout même écran verrouillé (Care PR #9 fusionnée et livrée à
Emergent par fichiers bruts ; Famille PR #1 fusionnée mais intégrée à la main par l'agent Emergent,
copie Emergent en avance sur GitHub). Mémoire : PR #10 et #11.

1. **Tests réels écran verrouillé**, sur l'adresse Care ET l'adresse Famille, sur chaque téléphone :
   (a) enregistrer 2 min sans toucher l'écran → l'écran doit rester allumé, réécoute complète ;
   (b) verrouiller 30 s avec le bouton, déverrouiller, arrêter, réécouter. Si message « micro coupé » :
   noter téléphone + navigateur, capture.
2. **Racontelle Famille → GitHub** : dans Emergent Famille, Save to GitHub sur une NOUVELLE branche
   `emergent-famille-17-10` (jamais `main`, jamais « Forcer le push »). Puis Claude : relire le diff de
   l'agent (record.tsx), comparer à `main`, remettre `main` à jour proprement par PR.
   Ne PAS faire de Save to GitHub pour Care (GitHub est plus complet qu'Emergent).
3. **APK Care 1.0.5** (versionCode 6 : envoi audio corrigé + enregistrement écran verrouillé) :
   `git pull` puis build EAS, installer PAR-DESSUS la 1.0.3 (3 souvenirs en attente depuis le 16/10),
   accepter l'autorisation des notifications, vérifier `POST /api/capsules/…/audio 200` dans Railway.
4. **Mot de passe oublié** : tester une vraie réception d'email (Resend) depuis l'adresse Care.
5. **Mode d'emploi EHPAD** : lien d'installation APK 1.0.5, contact, et consigne « désactiver la mise
   en veille de l'écran pendant l'atelier » (version web) ; puis l'envoyer.
6. Plus tard : iPhone/Safari (session web, micro écran verrouillé) ; PR #2 + `api.racontellecare.com` ;
   bucket vide `racontelle-care-audio` ; comptes d'avant le 7/10 ; envoi mobile de Famille avant tout APK.

Rappel permanent : ne pas faire « Save to GitHub » depuis Emergent (sa copie n'a pas les PR fusionnées sur GitHub).

## Architecture en production (au 16/10/2026)

| Élément | Où | Détail |
|---------|----|--------|
| API FastAPI | Railway, projet `vivacious-unity`, service `racontellecareapi`, EU West | `https://racontellecareapi-production.up.railway.app`, `Dockerfile` racine, redéploie à chaque fusion dans `main` |
| Base MongoDB | Railway | base neuve depuis le 7/10 ; les comptes d'avant le 7/10 sont dans l'ancienne base Emergent |
| Audios | Scaleway Object Storage, organisation « Racontelle », bucket **`racontelle-care-media`**, `fr-par` | variables `S3_*` ; clé API `railway-racontelle` (expire ~16/10/2027) ; `racontelle-care-audio` vide, inutilisé |
| Site web testeurs | aperçu Emergent `https://ehpad-recall.preview.emergentagent.com` | servi par Emergent depuis sa propre copie du frontend ; `frontend/.env` Emergent : `EXPO_PUBLIC_BACKEND_URL` = API Railway |
| APK Android | EAS (compte Expo `laracontelle`, projet `racontelle-care`), profil `preview` | `frontend/eas.json` → API Railway ; 1.0.5 (versionCode 6) = envoi audio corrigé + enregistrement écran verrouillé ; téléphone encore en 1.0.3 au 17/10 |
| Emails | Resend, `no-reply@racontellecare.com` | domaine vérifié via DNS Gandi (DKIM `resend._domainkey`, CNAME `send`, `rsend`) |
| Domaine | Gandi, `racontellecare.com` | ne pas toucher aux enregistrements messagerie Gandi existants |

Variables Railway attendues (noms seulement) : `MONGO_URL`, `DB_NAME`, `JWT_*`, `CORS_ORIGINS`,
`CORS_PROXY_ORIGIN`, `CORS_PUBLIC_ORIGIN`, `S3_BUCKET`, `S3_ENDPOINT`, `S3_REGION`,
`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`,
`PASSWORD_RESET_URL`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`. Ne jamais écrire de valeur secrète
dans le dépôt.

## Pièges déjà rencontrés (ne pas les refaire)

- **Emergent écrit directement dans `main`** et garde sa propre copie. Il **ne peut pas faire de
  `git pull`** dans un projet en cours (confirmé le 17/10), et importer le dépôt crée un nouveau projet
  avec une **nouvelle adresse** (à éviter : les testeurs ont l'adresse actuelle). Pour livrer un
  changement du frontend au site testeurs : demander à l'agent Emergent de remplacer les fichiers
  modifiés par leur version brute `https://raw.githubusercontent.com/Racontelle26/racontellecareapi/main/<chemin>`
  (dépôt public), puis de redémarrer Expo en vidant le cache, sans Save to GitHub. Dépôt privé
  (Racontelle Famille) : lui joindre un correctif `git apply`. Ne jamais « forcer le push » depuis
  Emergent : sa copie n'a pas les PR fusionnées sur GitHub.
- **Expo SDK 57** remplace `fetch` par `expo/fetch`, qui refuse les parties FormData `{ uri, name, type }`.
  Envoi de fichiers sur mobile : `FileSystem.uploadAsync` (`frontend/src/api.ts`, `uploadNativeFile`).
- **Site et API sur deux sites différents** : le cookie de session web doit être
  `SameSite=None; Secure; HttpOnly; Partitioned` (`backend/security.py`, `_set_refresh_cookie`),
  sinon déconnexion à chaque rechargement. Non testé sur Safari/iPhone. Solution durable :
  `app.racontellecare.com` (PR #2) + domaine `api.racontellecare.com` sur Railway.
- **Écran verrouillé pendant un récit** (17/10 : fichier web de 26 s pour un compteur à 4 min) :
  l'enregistrement doit CONTINUER jusqu'à l'arrêt par l'animatrice (exigence de l'utilisatrice).
  APK ≥ 1.0.5 : `enableBackgroundRecording` (plugin expo-audio) + `allowsBackgroundRecording`, avec
  l'autorisation des notifications (Android 13+, sinon pause + message). Web : écran gardé allumé
  (Wake Lock + vidéo muette, `src/screen-awake.ts`) ; si le navigateur coupe malgré tout le micro,
  on le détecte au retour et on garde le début avec sa vraie durée. Ne jamais arrêter de soi-même.
  Le site testeurs est servi par Emergent : un changement du frontend n'y arrive qu'après
  « git pull » de `main` + redémarrage du frontend côté Emergent.
- Les journaux d'un déploiement Railway s'arrêtent quand il est remplacé : toujours ouvrir le
  déploiement **Active** le plus récent (Deployments → View logs → Network Logs).
- Sur mobile, un souvenir reste « en attente d'envoi » tant que `POST /api/capsules/{id}/audio`
  n'a pas répondu 200 ; l'envoi est retenté à l'ouverture, au retour au premier plan et après chaque
  sauvegarde. Ne jamais faire désinstaller l'APK : les audios en attente sont sur le téléphone.

## Commandes

- Tests backend (sans service externe) : `cd backend && python -m pytest tests_local -q -n 0`
- Frontend : `cd frontend && yarn install --frozen-lockfile && npx tsc --noEmit && npx expo lint`
- APK : `cd frontend && git pull && npx eas-cli build --platform android --profile preview`
  (incrémenter `version` et `android.versionCode` dans `app.json` pour installer par-dessus).

## Racontelle Famille

Dépôt privé `Racontelle26/Racontelle-Famille`, site testeurs `https://family-stories-34.preview.emergentagent.com`
(frontend et serveur Emergent). **La copie Emergent est en avance sur GitHub** (record.tsx avec
`Alert`, `Shuffle`, `CloudArrowUp`, `localFilePart`, avatars, absents de `main`). PR #1 (17/10,
enregistrement écran verrouillé) a été écrite sur l'ancienne version ; l'agent Emergent l'a intégrée
à la main le 17/10 dans sa version (tsc + lint OK). Avant tout travail de code sur Famille : faire
pousser la copie Emergent sur une NOUVELLE branche GitHub, puis travailler depuis celle-ci.
Avant tout APK Famille : corriger l'envoi mobile (`fetch` + FormData `{ uri }` refusé par Expo SDK 57,
comme Care PR #4).

## Rappels programmés (scheduled tasks Claude)

- 4/01/2027 : fin de l'essai gratuit Scaleway le 14/01/2027 (moyen de paiement).
- 1/10/2027 : remplacer la clé Scaleway `railway-racontelle` (expire ~16/10/2027).
